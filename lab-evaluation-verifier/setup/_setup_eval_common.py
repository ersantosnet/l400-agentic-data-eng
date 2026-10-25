#!/usr/bin/env python3
"""
Shared helpers for the L400 Lab Setup evaluators (lab-evaluation-verifier/setup/).

Each setup evaluator (01/02/03) deep-checks that one lab GCP project was deployed
correctly by its lab pack (`lab-packs/partN-*/deploy.sh` / `deploy-all-labs.sh`):
required APIs, VPC/subnet/firewall, the Dataproc Serverless service account,
lab buckets (existence + region) and seed objects, BigQuery datasets (existence + region)
& connections (Part 3), and the optional Cloud Composer environment (Parts 2 & 3).

Supports both remote LLM grading via the Cloud Run validator (`eval_config_update-v1.sql` / `eval_config_update-v2.sql`)
and deterministic local verification (`--no-submit`).
"""

import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec  # noqa: E402

ec.apply_default_gcp_env()

LAB = ec.LAB
DEFAULT_VALIDATOR_URL = ec.DEFAULT_VALIDATOR_URL
SALT = ec.SALT

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

extract_ldap = ec.extract_ldap
is_service_account = ec.is_service_account
get_student_identity = ec.get_student_identity
calculate_signature = ec.calculate_signature
get_identity_token = ec.get_identity_token
submit_bundle = ec.submit_bundle
print_manual_instructions = ec.print_manual_instructions


# ---------------------------------------------------------------------------
# Project & region resolution
# ---------------------------------------------------------------------------

def resolve_project(part_num: int) -> tuple[str, str]:
    """Resolves (project_id, region) from CLI args, env vars, .lab-env.json, .env, tfvars, or default."""
    project_id, _, region = ec.resolve_gcp_context(
        part_num=part_num,
        script_file=__file__,
        fallback_default_project=True,
    )
    return project_id, region


# ---------------------------------------------------------------------------
# Check primitives (read-only gcloud / bq calls)
# ---------------------------------------------------------------------------

def _short_err(err: str) -> str:
    """Condenses noisy gcloud/bq stderr to its most relevant line."""
    lines = [ln.strip() for ln in (err or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    errors = [ln for ln in lines if ln.startswith("ERROR") or "NOT_FOUND" in ln or "PERMISSION_DENIED" in ln]
    msg = errors[-1] if errors else lines[-1]
    return msg[:300]


def _run(cmd: list, timeout: int = 60) -> tuple:
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=ec.build_gcp_subprocess_env(),
        )
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
    rc, out, err = _run(
        ["gcloud", "services", "list", "--enabled", f"--project={project}", "--format=value(config.name)"],
        timeout=90,
    )
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
    return _result("VPC, subnet & firewall", PASS, f"{vpc} / {subnet} ({region}) / {firewall}")


def check_service_account(project: str, account_id: str = "sa-dataproc-serverless") -> dict:
    email = f"{account_id}@{project}.iam.gserviceaccount.com"
    rc, _, err = _run(["gcloud", "iam", "service-accounts", "describe", email, f"--project={project}", "--format=value(email)"])
    if rc == 0:
        return _result("Dataproc Serverless service account", PASS, email)
    return _result("Dataproc Serverless service account", FAIL, err or f"{email} not found")


def check_buckets(project: str, suffixes: list, region: str = "") -> dict:
    missing = []
    wrong_region = []
    for suffix in suffixes:
        bucket = f"gs://{project}-{suffix}"
        rc, out, _ = _run(["gcloud", "storage", "buckets", "describe", bucket, f"--project={project}", "--format=json"])
        if rc != 0:
            missing.append(bucket)
            continue
        if region:
            meta = ec.safe_json_loads(out, {})
            actual_loc = str(meta.get("location") or "").strip() if isinstance(meta, dict) else ""
            if actual_loc and actual_loc.lower() != region.lower():
                wrong_region.append(f"{bucket} in {actual_loc} (expected {region})")
    problems = []
    if missing:
        problems.append("Missing: " + ", ".join(missing))
    if wrong_region:
        problems.append("Region mismatch: " + ", ".join(wrong_region))
    if problems:
        return _result("Lab buckets", FAIL, "; ".join(problems))
    loc_suffix = f" ({region})" if region else ""
    return _result("Lab buckets", PASS, ", ".join(f"{project}-{s}" for s in suffixes) + loc_suffix)


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
    objects = [
        line.strip()
        for line in out.splitlines()
        if line.strip().startswith("gs://") and not line.strip().endswith("/") and not line.strip().endswith(":")
    ]
    problems = []
    if len(objects) < min_count:
        problems.append(f"found {len(objects)} objects, expected >= {min_count}")
    for pfx in (required_prefixes or []):
        if not any(f"/{pfx}/" in o for o in objects):
            problems.append(f"missing feed '{pfx}/'")
    if problems:
        return _result(name, FAIL, "; ".join(problems))
    return _result(name, PASS, f"{len(objects)} objects under {prefix_uri}")


def check_bq_datasets(project: str, datasets: list, region: str = "") -> dict:
    missing = []
    wrong_region = []
    for ds in datasets:
        rc, out, _ = _run(["bq", "--headless", "-q", f"--project_id={project}", "show", "--format=prettyjson", f"{project}:{ds}"])
        if rc != 0:
            missing.append(ds)
            continue
        if region:
            meta = ec.safe_json_loads(out, {})
            actual_loc = str(meta.get("location") or "").strip() if isinstance(meta, dict) else ""
            if actual_loc and actual_loc.lower() != region.lower():
                wrong_region.append(f"{ds} in {actual_loc} (expected {region})")
    problems = []
    if missing:
        problems.append("Missing: " + ", ".join(missing))
    if wrong_region:
        problems.append("Region mismatch: " + ", ".join(wrong_region))
    if problems:
        return _result("BigQuery datasets", FAIL, "; ".join(problems))
    loc_suffix = f" ({region})" if region else ""
    return _result("BigQuery datasets", PASS, ", ".join(datasets) + loc_suffix)


def check_bq_connection(project: str, region: str, connection_id: str) -> dict:
    ref = f"{project}.{region}.{connection_id}"
    rc, _, err = _run(["bq", "--headless", "-q", f"--project_id={project}", f"--location={region}", "show", "--connection", "--format=none", ref])
    if rc == 0:
        return _result("BigQuery Cloud Resource connection", PASS, ref)
    return _result("BigQuery Cloud Resource connection", FAIL, err or f"{ref} not found")


def check_composer(project: str, region: str, env_name: str) -> dict:
    rc, out, err = _run(
        ["gcloud", "composer", "environments", "describe", env_name, f"--location={region}", f"--project={project}", "--format=value(state)"],
        timeout=90,
    )
    if rc != 0:
        if "NOT_FOUND" in err or "not found" in err.lower() or "was not found" in err.lower():
            return _result("Cloud Composer environment (optional)", SKIP, f"'{env_name}' not deployed in {region} (deploy.sh --enable-composer is opt-in)")
        return _result("Cloud Composer environment (optional)", SKIP, err or f"Could not describe '{env_name}'")
    if out == "RUNNING":
        return _result("Cloud Composer environment (optional)", PASS, f"{env_name} RUNNING ({region})")
    return _result("Cloud Composer environment (optional)", FAIL, f"{env_name} state is {out or 'UNKNOWN'} (expected RUNNING)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_setup_eval(part_num: int, eval_name: str, title: str, build_checks) -> int:
    """Runs one setup evaluator. build_checks(project, region) -> list of check result dicts."""
    start_time = time.time()
    zip_filename = f"{eval_name}.zip"
    zip_path = ec.resolve_zip_path(__file__, zip_filename)
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

    local_passed = all(r["status"] in (PASS, SKIP) for r in results)

    no_submit = "--no-submit" in sys.argv or os.environ.get("NO_SUBMIT") == "1"
    force_manual = "--manual" in sys.argv or os.environ.get("MANUAL") == "1"
    require_remote = "--require-remote" in sys.argv or os.environ.get("EVAL_REQUIRE_REMOTE") == "1"

    # Resolve identity token first so manifest.json matches the Bearer token identity
    student_account, student_ldap, token, auth_account = ec.resolve_submission_identity(
        DEFAULT_VALIDATOR_URL,
        force_manual=force_manual,
        no_submit=no_submit,
    )
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
        z.writestr(
            "setup_checks.json",
            json.dumps(
                {
                    "project_id": project_id,
                    "region": region,
                    "part": part_num,
                    "passed": local_passed,
                    "results": results,
                },
                indent=2,
            ),
        )
    print(f"\n✔ Created evaluation package: {zip_filename} ({student_ldap})")

    if no_submit:
        print("ℹ Submission skipped (--no-submit).")
        exit_code = ec.EXIT_PASS if local_passed else ec.EXIT_EVAL_FAIL
    else:
        is_localhost = "localhost" in DEFAULT_VALIDATOR_URL or "127.0.0.1" in DEFAULT_VALIDATOR_URL
        if not force_manual and (is_localhost or token):
            if token:
                acc_label = f" ({auth_account})" if auth_account else ""
                print(f"✔ Authenticated with Google Cloud identity token{acc_label}.")
            print(f"Submitting {zip_filename} to validator ({DEFAULT_VALIDATOR_URL})...")
            status, response_text = submit_bundle(DEFAULT_VALIDATOR_URL, zip_path, eval_name, token)
            try:
                parsed = json.loads(response_text)
                print(json.dumps(parsed, indent=2))
            except Exception:
                if response_text:
                    print(response_text)

            if status in (200, 201):
                verdict, reasoning, remote_exit = ec.parse_validator_verdict(status, response_text)
                ec.print_remote_verdict_callout(verdict, reasoning)
                exit_code = ec.EXIT_PASS if (local_passed and remote_exit == ec.EXIT_PASS) else ec.EXIT_EVAL_FAIL
            elif (
                status == 404
                and "Evaluation prompt not found" in (response_text or "")
                and not require_remote
            ):
                print(
                    f"ℹ Remote setup rubric for '{eval_name}' not yet seeded in BigQuery (HTTP 404); "
                    "using deterministic local setup verification."
                )
                ec.print_remote_verdict_callout(
                    "PASSED" if local_passed else "FAILED",
                    "Evaluated via deterministic local setup checks (HTTP 404 prompt not yet seeded in BigQuery).",
                )
                exit_code = ec.EXIT_PASS if local_passed else ec.EXIT_EVAL_FAIL
            else:
                verdict, reasoning, remote_exit = ec.parse_validator_verdict(status, response_text)
                ec.print_remote_verdict_callout(verdict, reasoning)
                if not local_passed:
                    exit_code = ec.EXIT_EVAL_FAIL
                else:
                    exit_code = remote_exit if remote_exit in (ec.EXIT_EVAL_FAIL, ec.EXIT_MANUAL_UNGRADED) else ec.EXIT_MANUAL_UNGRADED
        else:
            print_manual_instructions(zip_filename)
            verdict, reasoning, _ = ec.parse_validator_verdict(0, "", is_manual=True)
            ec.print_remote_verdict_callout(verdict, reasoning)
            exit_code = ec.EXIT_MANUAL_UNGRADED if local_passed else ec.EXIT_EVAL_FAIL

    print("")
    if exit_code == ec.EXIT_PASS:
        print(f"✔ L400-SETUP-GATE-PASS • Part {part_num} lab deployment verified in {project_id} ({region})")
    else:
        print(f"✗ L400-SETUP-GATE-FAIL • Part {part_num} lab deployment has issues in {project_id} ({region})")
        print(f"  Fix the items above (re-run lab-packs deploy for Part {part_num} with --region={region}) and run this check again.")

    print(f"\nDone! (Project: {project_id} | Region: {region} | Elapsed: {time.time() - start_time:.2f}s)")
    return exit_code
