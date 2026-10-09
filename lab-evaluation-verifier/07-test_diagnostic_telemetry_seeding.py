#!/usr/bin/env python3
"""
Lab Evaluation: L400-agentic-solution-eng - diagnostic_telemetry_seeding
Queries and verifies baseline seeding for diagnostic telemetry tables.
Supports both Automatic submission (local proxy) and Manual submission (web upload).
"""

import os
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

LAB = "L400-agentic-solution-eng"
EVAL_NAME = "diagnostic_telemetry_seeding"
ZIP_FILENAME = f"{EVAL_NAME}.zip"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app")
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")


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
    """Discovers active gcloud account and extracts LDAP identity.
    Filters out machine/VM service accounts (such as Cloudtop shared service accounts)
    and prioritizes authenticated human accounts (@google.com or @*.altostrat.com).
    """
    account = ""
    # 1. Check if active gcloud account is a human user
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

    # 2. If active account is missing or a service account (e.g. Cloudtop VM service account),
    # search credentialed accounts in gcloud auth list
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

    # 3. Fallback to OS USER environment variable (corporate LDAP on Cloudtop/macOS)
    if not account:
        os_user = os.environ.get("USER", "").strip()
        if os_user and not is_service_account(os_user):
            account = f"{os_user}@google.com"
        else:
            account = "unknown@google.com"

    student_ldap = extract_ldap(account)
    return account, student_ldap


def get_gcp_context():
    """Reads project and dataset configurations from agent-config.json or gcloud."""
    project_id = ""
    dataset = ""
    region = ""

    if os.path.exists("agent-config.json"):
        try:
            with open("agent-config.json", "r") as f:
                cfg = json.load(f)
                project_id = cfg.get("gcp-project-id", "")
                dataset = cfg.get("bigquery-dataset", "")
                region = cfg.get("cloud-run-region") or cfg.get("artifact-registry-location", "")
        except Exception:
            pass

    if not project_id or project_id == "null":
        try:
            res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
                project_id = res.stdout.strip()
        except Exception:
            pass

    return project_id, dataset, region


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
    """Retrieves Google identity token for authenticating directly against Cloud Run.
    Explicitly prioritizes an authenticated @google.com account so Cloud Run invoker
    permissions succeed even when an Argolis/lab account is the active gcloud account.
    Returns (token, account_used).
    """
    # 1. Search gcloud auth list for an authenticated @google.com account
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

    # 2. Fallback to active gcloud account
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
        f"L400-agentic-solution-eng".encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="evaluation"',
        b"",
        f"diagnostic_telemetry_seeding".encode("utf-8"),
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
    """Queries diagnostic telemetry baseline tables."""
    project_id, dataset, _ = get_gcp_context()
    dataset = dataset or "l400_agentic_se"
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Querying diagnostic telemetry tables in {project_id}:{dataset}...")
    def run_query(sql):
        cmd = ["bq", "query", "--use_legacy_sql=false", "--format=prettyjson", sql]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            try:
                return safe_json_loads(p.stdout, {"error": p.stderr.strip() or "Query failed"}) if (p.returncode == 0 and p.stdout.strip()) else {"error": p.stderr.strip() or "Query failed"}
            except Exception:
                return {"raw": p.stdout}
        return {"error": p.stderr.strip() or "Query failed"}

    summary = {
        "inventory_levels": run_query(f"""
            SELECT 
              COUNT(*) as total_rows, 
              COUNT(DISTINCT product_sku) as distinct_skus,
              MIN(stock_available) as min_stock,
              MAX(stock_available) as max_stock,
              ARRAY_AGG(DISTINCT warehouse_region) as warehouses
            FROM `{project_id}.{dataset}.inventory_levels`
        """),
        "gtm_tag_health": run_query(f"""
            SELECT 
              COUNT(*) as total_rows,
              ARRAY_AGG(DISTINCT firing_status) as distinct_statuses
            FROM `{project_id}.{dataset}.gtm_tag_health`
        """),
        "web_access_logs": run_query(f"""
            SELECT 
              COUNT(*) as total_rows,
              ROUND(SAFE_DIVIDE(COUNTIF(status_code = 200), COUNT(*)) * 100, 2) as http_200_pct,
              ROUND(AVG(latency_ms), 2) as avg_latency_ms
            FROM `{project_id}.{dataset}.web_access_logs`
        """)
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
        z.writestr("diagnostic_telemetry_summary.json", json.dumps(summary, indent=2))

    return created_at, signature


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(script_dir, ZIP_FILENAME)

    print("=======================================================")
    print(f" Lab Evaluation: L400-agentic-solution-eng - diagnostic_telemetry_seeding")
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
