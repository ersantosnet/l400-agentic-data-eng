#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part1 - velox_event_log_plan
Extracts physical execution plan and Velox native operator telemetry from the Spark event log in GCS.
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

LAB = "L400-da-data-engineering-part1"
EVAL_NAME = "velox_event_log_plan"
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

    return project_id, dataset, region or "us-central1"


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
    """Fetches the remediated Spark event log and extracts physical plan telemetry."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    bucket_uri = f"gs://{project_id}-spark-event-logs"
    print(f"Scanning Spark event logs in {bucket_uri} (project: {project_id})...")

    preseeded_names = (
        "current_event_log.json",
        "app-02-decelerated-udf.json",
        "app-02-remediated-nqe.json",
    )

    ls_proc = subprocess.run(["gcloud", "storage", "ls", f"{bucket_uri}/**", f"--project={project_id}"], capture_output=True, text=True, timeout=30)
    all_uris = [u.strip() for u in ls_proc.stdout.splitlines() if u.strip()] if ls_proc.returncode == 0 else []
    candidate_uris = [
        u for u in all_uris
        if not u.endswith("/") and "/archive/" not in u and not any(u.endswith(p) for p in preseeded_names)
    ]

    matched_uri = ""
    log_content = ""
    for uri in reversed(candidate_uris):
        cat_proc = subprocess.run(["gcloud", "storage", "cat", uri, f"--project={project_id}"], capture_output=True, text=True, timeout=45)
        if cat_proc.returncode == 0 and cat_proc.stdout.strip():
            matched_uri = uri
            log_content = cat_proc.stdout
            break

    plan_events = []
    for line in log_content.splitlines():
        if any(tok in line for tok in ("SparkListenerSQLAdaptiveExecutionUpdate", "SparkListenerSQLExecutionStart", "Velox", "Transformer", "BatchEvalPython")):
            plan_events.append(line[:4000])
            if len(plan_events) >= 25:
                break

    native_operators = [
        op for op in (
            "VeloxHashAggregate",
            "ProjectExecTransformer",
            "FilterExecTransformer",
            "BroadcastHashJoinExecTransformer",
            "ColumnarToRowExec",
            "VeloxColumnarToRow",
        )
        if op in log_content
    ]

    telemetry = {
        "project_id": project_id,
        "region": region,
        "event_log_bucket": bucket_uri,
        "all_event_log_uris": all_uris,
        "matched_remediated_event_log_uri": matched_uri or None,
        "has_batch_eval_python": "BatchEvalPython" in log_content if log_content else None,
        "detected_native_operators": native_operators,
        "plan_event_count": len(plan_events),
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
        z.writestr("velox_event_log_telemetry.json", json.dumps(telemetry, indent=2))
        if plan_events:
            z.writestr("event_log_plan_excerpt.txt", "\n".join(plan_events))

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
