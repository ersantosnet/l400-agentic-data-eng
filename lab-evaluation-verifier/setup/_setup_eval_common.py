#!/usr/bin/env python3
"""
Shared helpers for the L400 Lab Setup evaluators (lab-evaluation-verifier/setup/).

Each setup evaluator (01/02/03) deep-checks that one lab GCP project was deployed
correctly by its lab pack (`lab-packs/partN-*/deploy.sh` / `deploy-all-labs.sh`):
required APIs, VPC/subnet/firewall, the Dataproc Serverless service account,
lab buckets and seed objects, BigQuery datasets & connections (Part 3), and the
optional Cloud Composer environment (Parts 2 & 3).

Structure (identity discovery, signed bundle, Automatic/Manual submission) mirrors
lab-evaluation-verifier/part2/01-test_nqe_qualification_output.py. Unlike the part
evaluators, setup checks are also graded locally so CEs immediately see PASS/FAIL.
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
import time
from datetime import datetime, timezone

LAB = "L400-agentic-data-eng"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app")
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


# ---------------------------------------------------------------------------
# Identity & submission helpers (mirrors the part2 evaluator template)
# ---------------------------------------------------------------------------

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


def get_student_identity() -> tuple:
    """Discovers the active human gcloud account and extracts the LDAP identity."""
    account = ""
    try:
        result = subprocess.run(["gcloud", "config", "get-value", "account"], capture_output=True, text=True, timeout=5)
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
                    any_user = next((a["account"] for a in accounts if not is_service_account(a.get("account", ""))), None)
                    if any_user:
                        account = any_user
        except Exception:
            pass

    if not account:
        os_user = os.environ.get("USER", "").strip()
        account = f"{os_user}@google.com" if os_user and not is_service_account(os_user) else "unknown@google.com"

    return account, extract_ldap(account)


def calculate_signature(student_ldap: str, lab: str, evaluation: str, created_at: str, salt: str) -> str:
    """Generates SHA-256 signature for bundle anti-tampering."""
    raw = f"{student_ldap.strip().lower()}:{lab.strip().lower()}:{evaluation.strip().lower()}:{created_at.strip().lower()}:{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_identity_token() -> tuple:
    """Retrieves a Google identity token (prefers an authenticated @google.com account)."""
    try:
        out = subprocess.run(["gcloud", "auth", "list", "--format=json"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            accounts = json.loads(out.stdout)
            google_acc = next((acc["account"] for acc in accounts if acc.get("account", "").endswith("@google.com")), None)
            if google_acc:
                res = subprocess.run(
                    ["gcloud", "auth", "print-identity-token", f"--account={google_acc}"],
                    capture_output=True, text=True, timeout=10
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip(), google_acc
    except Exception:
        pass
    try:
        res = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip(), ""
    except Exception:
        pass
    return "", ""


def submit_bundle(validator_url: str, zip_path: str, eval_name: str, token: str = ""):
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
        eval_name.encode("utf-8"),
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

    req = urllib.request.Request(validator_url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=180) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8") if e.fp else str(e))
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


# ---------------------------------------------------------------------------
# Project resolution
# ---------------------------------------------------------------------------

def resolve_project(part_num: int) -> tuple:
    """Resolves (project_id, region) from CLI args, env vars, or the l400-agentic-de-pN-$USER default."""
    project_id = os.environ.get(f"P{part_num}_PROJECT_ID") or os.environ.get("PROJECT_ID") or ""
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
    if not project_id:
        user = re.sub(r"[^a-z0-9-]", "-", os.environ.get("USER", "your-ldap").lower()).strip("-") or "your-ldap"
        project_id = f"l400-agentic-de-p{part_num}-{user}"
    return project_id, region or "us-central1"


# ---------------------------------------------------------------------------
# Check primitives (read-only gcloud / bq calls)
# ---------------------------------------------------------------------------

def _short_err(err: str) -> str:
    """Condenses noisy gcloud/bq stderr to its most relevant line."""
    lines = [ln.strip() for ln in (err or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    errors = [ln for ln in lines if ln.startswith("ERROR") or "NOT_FOUND" in ln or "PERMISSION_DENIED" in ln]
    msg = (errors[-1] if errors else lines[-1])
    return msg[:300]


def _run(cmd: list, timeout: int = 60) -> tuple:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, (res.stdout or "").strip(), _short_err(res.stderr)
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s: {' '.join(cmd)}"


def _result(name: str, status: str, detail: str) -> dict:
    return {"check": name, "status": status, "detail": detail}


def check_project(project: str) -> dict:
    rc, out, err = _run(["gcloud", "projects", "describe", project, "--format=value(lifecycleState)"])
    if rc == 0 and out == "ACTIVE":
        return _result("Project exists & ACTIVE", PASS, project)
    return _result("Project exists & ACTIVE", FAIL, err or out or f"Project {project} not found or not accessible")


def check_apis(project: str, apis: list) -> dict:
    rc, out, err = _run(["gcloud", "services", "list", "--enabled", f"--project={project}", "--format=value(config.name)"], timeout=90)
    if rc != 0:
        return _result("Required APIs enabled", FAIL, err or "Could not list enabled services")
    enabled = set(out.split())
    missing = [a for a in apis if a not in enabled]
    if missing:
        return _result("Required APIs enabled", FAIL, "Missing: " + ", ".join(missing))
    return _result("Required APIs enabled", PASS, f"{len(apis)}/{len(apis)} enabled")


def check_network(project: str, region: str, vpc: str, subnet: str, firewall: str) -> dict:
    problems = []
    if _run(["gcloud", "compute", "networks", "describe", vpc, f"--project={project}", "--format=value(name)"])[0] != 0:
        problems.append(f"VPC '{vpc}' not found")
    if _run(["gcloud", "compute", "networks", "subnets", "describe", subnet, f"--region={region}", f"--project={project}", "--format=value(name)"])[0] != 0:
        problems.append(f"Subnet '{subnet}' ({region}) not found")
    if _run(["gcloud", "compute", "firewall-rules", "describe", firewall, f"--project={project}", "--format=value(name)"])[0] != 0:
        problems.append(f"Firewall rule '{firewall}' not found")
    if problems:
        return _result("VPC, subnet & firewall", FAIL, "; ".join(problems))
    return _result("VPC, subnet & firewall", PASS, f"{vpc} / {subnet} / {firewall}")


def check_service_account(project: str, account_id: str = "sa-dataproc-serverless") -> dict:
    email = f"{account_id}@{project}.iam.gserviceaccount.com"
    rc, _, err = _run(["gcloud", "iam", "service-accounts", "describe", email, f"--project={project}", "--format=value(email)"])
    if rc == 0:
        return _result("Dataproc Serverless service account", PASS, email)
    return _result("Dataproc Serverless service account", FAIL, err or f"{email} not found")


def check_buckets(project: str, suffixes: list) -> dict:
    missing = []
    for suffix in suffixes:
        bucket = f"gs://{project}-{suffix}"
        if _run(["gcloud", "storage", "buckets", "describe", bucket, f"--project={project}", "--format=value(name)"])[0] != 0:
            missing.append(bucket)
    if missing:
        return _result("Lab buckets", FAIL, "Missing: " + ", ".join(missing))
    return _result("Lab buckets", PASS, ", ".join(f"{project}-{s}" for s in suffixes))


def check_objects(project: str, name: str, uris: list) -> dict:
    missing = []
    for uri in uris:
        if _run(["gcloud", "storage", "ls", uri, f"--project={project}"])[0] != 0:
            missing.append(uri)
    if missing:
        return _result(name, FAIL, "Missing: " + ", ".join(missing))
    return _result(name, PASS, f"{len(uris)}/{len(uris)} seed objects present")


def check_object_count(project: str, name: str, prefix_uri: str, min_count: int, required_prefixes: list = None) -> dict:
    rc, out, err = _run(["gcloud", "storage", "ls", "--recursive", prefix_uri, f"--project={project}"], timeout=120)
    if rc != 0:
        return _result(name, FAIL, err or f"Could not list {prefix_uri}")
    objects = [line.strip() for line in out.splitlines() if line.strip().startswith("gs://") and not line.strip().endswith("/") and not line.strip().endswith(":")]
    problems = []
    if len(objects) < min_count:
        problems.append(f"found {len(objects)} objects, expected >= {min_count}")
    for pfx in (required_prefixes or []):
        if not any(f"/{pfx}/" in o for o in objects):
            problems.append(f"missing feed '{pfx}/'")
    if problems:
        return _result(name, FAIL, "; ".join(problems))
    return _result(name, PASS, f"{len(objects)} objects under {prefix_uri}")


def check_bq_datasets(project: str, datasets: list) -> dict:
    missing = []
    for ds in datasets:
        if _run(["bq", f"--project_id={project}", "show", "--format=none", f"{project}:{ds}"])[0] != 0:
            missing.append(ds)
    if missing:
        return _result("BigQuery datasets", FAIL, "Missing: " + ", ".join(missing))
    return _result("BigQuery datasets", PASS, ", ".join(datasets))


def check_bq_connection(project: str, region: str, connection_id: str) -> dict:
    ref = f"{project}.{region}.{connection_id}"
    rc, _, err = _run(["bq", f"--project_id={project}", f"--location={region}", "show", "--connection", "--format=none", ref])
    if rc == 0:
        return _result("BigQuery Cloud Resource connection", PASS, ref)
    return _result("BigQuery Cloud Resource connection", FAIL, err or f"{ref} not found")


def check_composer(project: str, region: str, env_name: str) -> dict:
    rc, out, err = _run(["gcloud", "composer", "environments", "describe", env_name, f"--location={region}", f"--project={project}", "--format=value(state)"], timeout=90)
    if rc != 0:
        if "NOT_FOUND" in err or "not found" in err.lower() or "was not found" in err.lower():
            return _result("Cloud Composer environment (optional)", SKIP, f"'{env_name}' not deployed (deploy.sh --enable-composer is opt-in)")
        return _result("Cloud Composer environment (optional)", SKIP, err or f"Could not describe '{env_name}'")
    if out == "RUNNING":
        return _result("Cloud Composer environment (optional)", PASS, f"{env_name} RUNNING")
    return _result("Cloud Composer environment (optional)", FAIL, f"{env_name} state is {out or 'UNKNOWN'} (expected RUNNING)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_setup_eval(part_num: int, eval_name: str, title: str, build_checks) -> int:
    """Runs one setup evaluator. build_checks(project, region) -> list of check result dicts."""
    start_time = time.time()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    zip_filename = f"{eval_name}.zip"
    zip_path = os.path.join(script_dir, zip_filename)
    project_id, region = resolve_project(part_num)

    print("=======================================================")
    print(f" Lab Evaluation: {LAB} - {eval_name}")
    print(f" {title}")
    print(f" Target Project: {project_id} ({region})")
    print("=======================================================")

    results = [check_project(project_id)]
    if results[0]["status"] == PASS:
        results.extend(build_checks(project_id, region))
    else:
        print("✗ Project is missing or not accessible; skipping resource checks.")

    width = max(len(r["check"]) for r in results)
    for r in results:
        icon = {"PASS": "✔", "FAIL": "✗", "SKIP": "–"}[r["status"]]
        print(f"  {icon} [{r['status']}] {r['check'].ljust(width)}  {r['detail']}")

    passed = all(r["status"] in (PASS, SKIP) for r in results)
    print("")
    if passed:
        print(f"✔ L400-SETUP-GATE-PASS • Part {part_num} lab deployment verified in {project_id}")
    else:
        print(f"✗ L400-SETUP-GATE-FAIL • Part {part_num} lab deployment has issues in {project_id}")
        print(f"  Fix the items above (re-run lab-packs deploy for Part {part_num}) and run this check again.")

    # Signed evidence bundle (same manifest format as the part evaluators)
    student_account, student_ldap = get_student_identity()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "lab": LAB,
        "evaluation": eval_name,
        "created_at": created_at,
        "student_ldap": student_ldap,
        "workstation_account": student_account,
        "signature": calculate_signature(student_ldap, LAB, eval_name, created_at, SALT),
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("setup_checks.json", json.dumps({
            "project_id": project_id,
            "region": region,
            "part": part_num,
            "passed": passed,
            "results": results,
        }, indent=2))
    print(f"\n✔ Created evaluation package: {zip_filename} ({student_ldap})")

    no_submit = "--no-submit" in sys.argv or os.environ.get("NO_SUBMIT") == "1"
    force_manual = "--manual" in sys.argv or os.environ.get("MANUAL") == "1"
    if no_submit:
        print("ℹ Submission skipped (--no-submit).")
    else:
        is_localhost = "localhost" in DEFAULT_VALIDATOR_URL or "127.0.0.1" in DEFAULT_VALIDATOR_URL
        token, _ = ("", "") if (is_localhost or force_manual) else get_identity_token()
        if not force_manual and (is_localhost or token):
            print(f"Submitting {zip_filename} to validator ({DEFAULT_VALIDATOR_URL})...")
            status, response_text = submit_bundle(DEFAULT_VALIDATOR_URL, zip_path, eval_name, token)
            if status in (200, 201):
                print("✔ Submitted to validator.")
            else:
                print(f"ℹ Validator did not accept the setup bundle (HTTP {status}). Your local result above still applies.")
        else:
            print_manual_instructions(zip_filename)

    print(f"\nDone! (Project: {project_id} | Elapsed: {time.time() - start_time:.2f}s)")
    return 0 if passed else 1
