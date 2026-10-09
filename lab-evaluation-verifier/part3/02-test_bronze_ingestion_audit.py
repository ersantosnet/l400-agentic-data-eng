#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - bronze_ingestion_audit
Extracts schemas, row counts, and audit column counts for the 5 Bronze Iceberg V2 tables in fraud_detection_db.
Supports both Automatic submission (local proxy / Cloud Run validator) and Manual submission (web upload).
"""

import os
import re
import sys
import json
import uuid
import hashlib
import zipfile
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone

LAB = "L400-da-data-engineering-part3"
EVAL_NAME = "bronze_ingestion_audit"
ZIP_FILENAME = f"{EVAL_NAME}.zip"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app")
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")

DOMAINS = [
    "customers_crm",
    "merchants_stores",
    "device_auth_logs",
    "payment_transactions",
    "chargeback_disputes",
]


def extract_ldap(account_str: str) -> str:
    """Extracts base corporate LDAP identity from Google email or Argolis account."""
    if not account_str:
        return ""
    acc = str(account_str).strip().lower()
    if "@" not in acc:
        return acc
    user, domain = acc.split("@", 1)
    if "altostrat.com" in domain:
        parts = domain.split(".")
        if parts[0] != "altostrat":
            return parts[0]
        return user
    return user


def is_service_account(acc: str) -> bool:
    """Checks if an account string represents a GCP service account rather than a human student."""
    if not acc:
        return False
    acc_lower = str(acc).strip().lower()
    return (
        "gserviceaccount.com" in acc_lower
        or "cloudtop" in acc_lower
        or acc_lower.startswith("service-")
    )


def get_student_identity() -> tuple[str, str]:
    """Discovers active gcloud account and extracts LDAP identity."""
    account = ""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "(unset)":
            candidate = result.stdout.strip()
            if not is_service_account(candidate):
                account = candidate
    except Exception:
        pass

    if not account:
        try:
            out = subprocess.run(["gcloud", "auth", "list", "--format=json"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0 and out.stdout.strip():
                accounts = json.loads(out.stdout)
                google_acc = next((a["account"] for a in accounts if a.get("account", "").endswith("@google.com")), None)
                if google_acc:
                    account = google_acc
                else:
                    argolis_acc = next((a["account"] for a in accounts if "altostrat.com" in a.get("account", "") and not is_service_account(a.get("account", ""))), None)
                    if argolis_acc:
                        account = argolis_acc
                    else:
                        any_user = next((a["account"] for a in accounts if not is_service_account(a.get("account", ""))), None)
                        if any_user:
                            account = any_user
        except Exception:
            pass

    if not account:
        os_user = os.environ.get("USER", "").strip()
        if os_user and not is_service_account(os_user):
            account = f"{os_user}@google.com"
        else:
            account = "unknown@google.com"

    student_ldap = extract_ldap(account)
    return account, student_ldap


def get_gcp_context() -> tuple[str, str, str]:
    """Reads project, dataset, and region configurations from CLI args, env vars, agent-config.json, terraform.tfvars, or gcloud."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or ""
    dataset = os.environ.get("BIGQUERY_DATASET", "")
    region = os.environ.get("REGION") or os.environ.get("GCP_REGION") or ""

    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in ("--project-id", "--project") and i + 1 < len(argv):
            project_id = argv[i + 1].strip()
        elif arg.startswith("--project-id=") or arg.startswith("--project="):
            project_id = arg.split("=", 1)[1].strip()
        elif arg == "--region" and i + 1 < len(argv):
            region = argv[i + 1].strip()
        elif arg.startswith("--region="):
            region = arg.split("=", 1)[1].strip()

    for cfg_path in ("agent-config.json", "../agent-config.json", "../../agent-config.json"):
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    project_id = project_id or cfg.get("gcp-project-id", "")
                    dataset = dataset or cfg.get("bigquery-dataset", "")
                    region = region or cfg.get("cloud-run-region") or cfg.get("artifact-registry-location", "")
            except Exception:
                pass

    if not project_id:
        for tfvars_path in ("terraform/terraform.tfvars", "../terraform/terraform.tfvars", "../../terraform/terraform.tfvars"):
            if os.path.exists(tfvars_path):
                try:
                    with open(tfvars_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    m_proj = re.search(r'project_id\s*=\s*"([^"]+)"', content)
                    if m_proj and m_proj.group(1) and "your-" not in m_proj.group(1):
                        project_id = m_proj.group(1).strip()
                    m_reg = re.search(r'region\s*=\s*"([^"]+)"', content)
                    if m_reg and not region:
                        region = m_reg.group(1).strip()
                except Exception:
                    pass

    if not project_id or project_id == "null":
        try:
            res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
                project_id = res.stdout.strip()
        except Exception:
            pass

    return project_id, dataset or "fraud_detection_db", region or "us-central1"


def safe_json_loads(text: str, default=None):
    """Safely decodes JSON text, returning default if empty or invalid."""
    if not text or not str(text).strip():
        return default if default is not None else {}
    try:
        return json.loads(text)
    except Exception:
        return default if default is not None else {"raw_output": str(text).strip()}


def calculate_signature(student_ldap: str, lab: str, evaluation: str, created_at: str, salt: str) -> str:
    """Generates SHA-256 signature for bundle anti-tampering."""
    raw = f"{student_ldap.strip().lower()}:{lab.strip().lower()}:{evaluation.strip().lower()}:{created_at.strip().lower()}:{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_identity_token() -> tuple[str, str]:
    """Retrieves Google identity token for authenticating directly against Cloud Run."""
    try:
        out = subprocess.run(["gcloud", "auth", "list", "--format=json"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            accounts = json.loads(out.stdout)
            google_acc = next((acc["account"] for acc in accounts if acc.get("account", "").endswith("@google.com")), None)
            if google_acc:
                res = subprocess.run(
                    ["gcloud", "auth", "print-identity-token", f"--account={google_acc}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip(), google_acc
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if res.returncode == 0 and res.stdout.strip():
            active_acc = ""
            try:
                acc_res = subprocess.run(["gcloud", "config", "get-value", "account"], capture_output=True, text=True, timeout=3)
                if acc_res.returncode == 0:
                    active_acc = acc_res.stdout.strip()
            except Exception:
                pass
            return res.stdout.strip(), active_acc
    except Exception:
        pass

    return "", ""


def run_bq_query(project_id: str, sql: str):
    """Runs a BigQuery SQL query and returns parsed JSON rows or error dict."""
    cmd = ["bq", "query", f"--project_id={project_id}", "--use_legacy_sql=false", "--format=prettyjson", sql]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        return safe_json_loads(p.stdout, {"error": p.stderr.strip() or "Query failed"})
    return {"error": (p.stderr or p.stdout or "Query failed").strip()}


def submit_bundle(validator_url: str, zip_path: str, token: str = ""):
    """Submits the zip bundle to the Cloud Run validator endpoint."""
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    filename = os.path.basename(zip_path)

    with open(zip_path, "rb") as f:
        file_bytes = f.read()

    body_parts = [
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="lab"',
        b"",
        LAB.encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="evaluation"',
        b"",
        EVAL_NAME.encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        f'Content-Disposition: form-data; name="files"; filename="{filename}"'.encode("utf-8"),
        b"Content-Type: application/zip",
        b"",
        file_bytes,
        f"--{boundary}--".encode("utf-8"),
        b""
    ]
    body = bytes([13, 10]).join(body_parts)

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "User-Agent": "lab-evaluation-client/1.0"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-User-Token"] = token

    req = urllib.request.Request(
        validator_url,
        data=body,
        headers=headers,
        method="POST"
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=180) as response:
            resp_body = response.read().decode("utf-8")
            status = response.status
            return status, resp_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, err_body
    except Exception as e:
        return 0, f"Failed to connect to validator at {validator_url}: {e}"


def print_manual_instructions(zip_filename: str):
    """Prints manual instructions for downloading and uploading the bundle."""
    print("=======================================================")
    print(" [Manual Submission Instructions]")
    print(f" 1. In VS Code file explorer: Right-click '{zip_filename}'")
    print(" 2. Select 'Download...' to save it to your local machine")
    print(" 3. Open the Lab Verifier Summary Portal in your browser")
    print(" 4. Click 'Manual Upload' at the top of the page")
    print(f" 5. Drag and drop '{zip_filename}' into the drop zone")
    print("=======================================================")


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Extracts schemas and row/audit column counts for all 5 Bronze tables."""
    project_id, dataset, region = get_gcp_context()
    dataset = "fraud_detection_db"
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Querying 5 Bronze tables in {project_id}:{dataset}...")
    bronze_results = {}

    for dom in DOMAINS:
        tbl = f"{dom}_bronze"
        show_proc = subprocess.run(
            ["bq", "show", "--format=prettyjson", f"{project_id}:{dataset}.{tbl}"],
            capture_output=True,
            text=True
        )
        if show_proc.returncode != 0 or not show_proc.stdout.strip():
            bronze_results[tbl] = {
                "exists": False,
                "error": (show_proc.stderr or show_proc.stdout or "Table not found").strip(),
            }
            continue

        meta = safe_json_loads(show_proc.stdout, {})
        cols = [f.get("name") for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict)]
        has_audit_cols = ("_ingestion_timestamp" in cols) and ("_source_file" in cols)

        if has_audit_cols:
            sql = f"SELECT COUNT(*) AS cnt, COUNT(_ingestion_timestamp) AS ts_cnt, COUNT(_source_file) AS src_cnt FROM `{project_id}.{dataset}.{tbl}`"
        else:
            sql = f"SELECT COUNT(*) AS cnt, -1 AS ts_cnt, -1 AS src_cnt FROM `{project_id}.{dataset}.{tbl}`"

        q_res = run_bq_query(project_id, sql)
        bronze_results[tbl] = {
            "exists": True,
            "columns": cols,
            "has_audit_columns": has_audit_cols,
            "table_metadata": meta,
            "row_and_audit_counts": q_res,
        }

    telemetry = {
        "project_id": project_id,
        "dataset": dataset,
        "region": region,
        "bronze_tables": bronze_results,
    }

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature = calculate_signature(student_ldap, LAB, EVAL_NAME, created_at, SALT)

    manifest_data = {
        "lab": LAB,
        "evaluation": EVAL_NAME,
        "created_at": created_at,
        "student_ldap": student_ldap,
        "workstation_account": student_account,
        "signature": signature
    }

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest_data, indent=2))
        z.writestr("bronze_ingestion_audit.json", json.dumps(telemetry, indent=2))

    return created_at, signature


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(script_dir, ZIP_FILENAME)

    print("=======================================================")
    print(f" Lab Evaluation: {LAB} - {EVAL_NAME}")
    print("=======================================================")

    student_account, student_ldap = get_student_identity()
    created_at, signature = create_bundle(zip_path, student_account, student_ldap)

    print(f"✔ Created evaluation package: {ZIP_FILENAME}")
    print(f"  Student Identity: {student_ldap} ({student_account})")
    print(f"  Timestamp:        {created_at}")
    print("")

    force_manual = "--manual" in sys.argv or os.environ.get("MANUAL") == "1"
    is_localhost = "localhost" in DEFAULT_VALIDATOR_URL or "127.0.0.1" in DEFAULT_VALIDATOR_URL
    token, auth_account = ("", "") if (is_localhost or force_manual) else get_identity_token()

    can_submit = not force_manual and (is_localhost or bool(token))

    if can_submit:
        if token:
            acc_label = f" ({auth_account})" if auth_account else ""
            print(f"✔ Authenticated with Google Cloud identity token{acc_label}.")
        print(f"Submitting {ZIP_FILENAME} to validator ({DEFAULT_VALIDATOR_URL})...")
        print("")
        status, response_text = submit_bundle(DEFAULT_VALIDATOR_URL, zip_path, token)
        try:
            parsed = json.loads(response_text)
            print(json.dumps(parsed, indent=2))
        except Exception:
            print(response_text)

        if status not in (200, 201):
            print("")
            print("Automatic submission did not succeed. You can submit manually:")
            print_manual_instructions(ZIP_FILENAME)
    else:
        if force_manual:
            print("Manual submission mode requested (--manual/MANUAL=1).")
        else:
            print("ℹ Google Cloud identity token could not be acquired (ensure 'gcloud auth login' has been run).")
            print("Proceeding with manual web submission.")
            print("")
        print_manual_instructions(ZIP_FILENAME)

    print("\nDone!")


if __name__ == "__main__":
    main()
