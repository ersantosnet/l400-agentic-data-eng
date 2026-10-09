#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - governance_composer_lineage
Verifies staged Cloud Composer 3 DAG (medallion_lakehouse_dag.py), Policy Tags on Bronze ssn columns,
Dataplex Knowledge Catalog Aspect Type (medallion-governance-template), Data Mesh (FraudDomain / FraudRiskFeatureStore),
Auto Data Quality scan, and OpenLineage processes.
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
EVAL_NAME = "governance_composer_lineage"
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


def get_access_token() -> str:
    """Retrieves Google Cloud OAuth2 access token for REST API calls."""
    try:
        res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def api_get(url: str, access_token: str, quota_project: str = "") -> tuple[int, dict]:
    """Calls a GCP REST API GET endpoint and returns (status_code, parsed_json)."""
    headers = {"Authorization": f"Bearer {access_token}"}
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, safe_json_loads(resp.read().decode("utf-8"), {})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, safe_json_loads(err_body, {"error": err_body})
    except Exception as e:
        return 0, {"error": str(e)}


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
    """Collects Composer DAG, Bronze Policy Tag metadata, Dataplex KC Aspect/Mesh, DQ Scans, and Lineage."""
    project_id, dataset, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    access_token = get_access_token()
    warehouse_bucket = f"gs://{project_id}-lakehouse-warehouse"
    dag_gcs_uri = f"{warehouse_bucket}/dags/medallion_lakehouse_dag.py"

    print(f"Checking Composer DAG, Policy Tags, Dataplex KC, DQ Scans, and Lineage in {project_id}...")

    # 1. Staged Composer DAG
    dag_ls = subprocess.run(
        ["gcloud", "storage", "ls", dag_gcs_uri, f"--project={project_id}"],
        capture_output=True,
        text=True
    )
    dag_staged_in_gcs = dag_ls.returncode == 0
    dag_content = ""
    if dag_staged_in_gcs:
        cat_proc = subprocess.run(
            ["gcloud", "storage", "cat", dag_gcs_uri, f"--project={project_id}"],
            capture_output=True,
            text=True
        )
        if cat_proc.returncode == 0:
            dag_content = cat_proc.stdout
    if not dag_content:
        for local_cand in (
            "dags/medallion_lakehouse_dag.py",
            "scripts/medallion_lakehouse_dag.py",
            "../../dags/medallion_lakehouse_dag.py",
            "../../scripts/medallion_lakehouse_dag.py",
            "../../lab-packs/part3/solution/medallion_lakehouse_dag.py",
        ):
            if os.path.exists(local_cand):
                try:
                    with open(local_cand, "r", encoding="utf-8") as f:
                        dag_content = f.read()
                    break
                except Exception:
                    pass

    # 2. Bronze Policy Tags on ssn columns
    bronze_policy_tags = {}
    for tbl in ("customers_crm_bronze", "payment_transactions_bronze"):
        show_proc = subprocess.run(
            ["bq", "show", "--format=prettyjson", f"{project_id}:fraud_detection_db.{tbl}"],
            capture_output=True,
            text=True
        )
        if show_proc.returncode == 0 and show_proc.stdout.strip():
            meta = safe_json_loads(show_proc.stdout, {})
            ssn_field = next((f for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict) and f.get("name") == "ssn"), {})
            ptags = ssn_field.get("policyTags", {}).get("names", []) if isinstance(ssn_field, dict) else []
            bronze_policy_tags[tbl] = {
                "exists": True,
                "ssn_policy_tags": ptags,
                "has_policy_tag": len(ptags) > 0,
            }
        else:
            bronze_policy_tags[tbl] = {
                "exists": False,
                "ssn_policy_tags": [],
                "has_policy_tag": False,
                "error": (show_proc.stderr or show_proc.stdout or "Table not found").strip(),
            }

    # 3. Dataplex Knowledge Catalog Aspect Type & Gold Entry Aspects
    asp_code, asp_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/aspectTypes/medallion-governance-template",
        access_token,
        project_id,
    )
    ent_code, gold_ent = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/entryGroups/@bigquery/entries/"
        f"bigquery.googleapis.com/projects/{project_id}/datasets/fraud_features_gold/tables/gold_fraud_features?view=ALL",
        access_token,
        project_id,
    )

    # 4. Dataplex Lakes & Data Products
    lakes_code, lakes_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/lakes",
        access_token,
        project_id,
    )
    dp_code, dp_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/dataProducts",
        access_token,
        project_id,
    )

    # 5. Dataplex Auto Data Quality Scans
    scans_code, scans_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/dataScans",
        access_token,
        project_id,
    )

    # 6. Data Lineage Processes
    lineage_processes = {}
    for loc in (region, "us"):
        lin_code, lin_resp = api_get(
            f"https://datalineage.googleapis.com/v1/projects/{project_id}/locations/{loc}/processes",
            access_token,
            project_id,
        )
        lineage_processes[loc] = {
            "status_code": lin_code,
            "processes": lin_resp.get("processes", []) if isinstance(lin_resp, dict) else [],
            "raw": lin_resp,
        }

    telemetry = {
        "project_id": project_id,
        "region": region,
        "composer_dag": {
            "gcs_uri": dag_gcs_uri,
            "staged_in_gcs": dag_staged_in_gcs,
        },
        "bronze_policy_tags": bronze_policy_tags,
        "aspect_type": {
            "status_code": asp_code,
            "response": asp_resp,
        },
        "gold_dataplex_entry": {
            "status_code": ent_code,
            "response": gold_ent,
        },
        "dataplex_lakes": {
            "status_code": lakes_code,
            "response": lakes_resp,
        },
        "dataplex_data_products": {
            "status_code": dp_code,
            "response": dp_resp,
        },
        "dataplex_data_scans": {
            "status_code": scans_code,
            "response": scans_resp,
        },
        "data_lineage": lineage_processes,
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
        z.writestr("governance_composer_lineage.json", json.dumps(telemetry, indent=2))
        if dag_content:
            z.writestr("medallion_lakehouse_dag.py", dag_content)

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
