#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part2 - nqe_qualification_output
Gathers NQE Qualification Tool TSV output (AppsRecommendedForBoost.tsv) from GCS.
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
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec

LAB = "L400-agentic-data-eng"
EVAL_NAME = "part2_nqe_qualification_output"
ZIP_FILENAME = f"{EVAL_NAME}.zip"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app")
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")

extract_ldap = ec.extract_ldap
is_service_account = ec.is_service_account
get_student_identity = ec.get_student_identity
safe_json_loads = ec.safe_json_loads
calculate_signature = ec.calculate_signature
get_identity_token = ec.get_identity_token
submit_bundle = ec.submit_bundle
print_manual_instructions = ec.print_manual_instructions


def get_gcp_context() -> tuple[str, str, str]:
    """Reads project, dataset, and region configurations via _eval_common.resolve_gcp_context."""
    return ec.resolve_gcp_context(part_num=2, script_file=__file__)


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Fetches NQE Qualification Tool TSV output from gs://<project_id>-nqe-audit-results/."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    bucket_uri = f"gs://{project_id}-nqe-audit-results"
    print(f"Checking NQE Qualification TSV output in {bucket_uri}...")

    tsv_patterns = [
        f"{bucket_uri}/*AppsRecommendedForBoost*.tsv",
        f"{bucket_uri}/**/*AppsRecommendedForBoost*.tsv",
        f"{bucket_uri}/*qualification*.tsv",
    ]
    tsv_content = ""
    matched_uri = ""
    all_matched_uris = []

    for pat in tsv_patterns:
        ls_proc = subprocess.run(
            ["gcloud", "storage", "ls", pat, f"--project={project_id}"],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            env=ec.build_gcp_subprocess_env(),
        )
        if ls_proc.returncode == 0 and ls_proc.stdout.strip():
            uris = [u.strip() for u in ls_proc.stdout.splitlines() if u.strip()]
            all_matched_uris.extend(uris)
            for first_uri in uris:
                cat_proc = subprocess.run(
                    ["gcloud", "storage", "cat", first_uri, f"--project={project_id}"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    stdin=subprocess.DEVNULL,
                    env=ec.build_gcp_subprocess_env(),
                )
                if cat_proc.returncode == 0 and cat_proc.stdout.strip():
                    tsv_content = cat_proc.stdout
                    matched_uri = first_uri
                    break
        if tsv_content:
            break

    audit_info = {
        "project_id": project_id,
        "region": region,
        "audit_bucket": bucket_uri,
        "matched_tsv_uri": matched_uri or None,
        "candidate_uris": list(dict.fromkeys(all_matched_uris)),
        "found": bool(tsv_content.strip()),
        "tsv_content": tsv_content,
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
        z.writestr("nqe_audit_files.json", json.dumps(audit_info, indent=2))
        if tsv_content:
            z.writestr("AppsRecommendedForBoost.tsv", tsv_content)

    return created_at, signature


def main():
    start_time = time.time()
    ec.apply_default_gcp_env()
    zip_path = ec.resolve_zip_path(__file__, ZIP_FILENAME)
    project_id, _, region = get_gcp_context()

    print("=======================================================")
    print(f" Lab Evaluation: {LAB} - {EVAL_NAME}")
    print(f" Target Project: {project_id or 'unknown'} ({region})")
    print("=======================================================")

    force_manual = "--manual" in sys.argv or os.environ.get("MANUAL") == "1"
    no_submit = "--no-submit" in sys.argv or os.environ.get("NO_SUBMIT") == "1"
    student_account, student_ldap, token, auth_account = ec.resolve_submission_identity(
        DEFAULT_VALIDATOR_URL, force_manual=force_manual, no_submit=no_submit
    )
    created_at, signature = create_bundle(zip_path, student_account, student_ldap)

    print(f"✔ Created evaluation package: {ZIP_FILENAME}")
    print(f"  Target Project:   {project_id or 'unknown'} ({region})")
    print(f"  Student Identity: {student_ldap} ({student_account})")
    print(f"  Timestamp:        {created_at}")
    print("")

    exit_code = ec.finalize_check_submission(
        EVAL_NAME,
        ZIP_FILENAME,
        zip_path,
        project_id,
        start_time,
        DEFAULT_VALIDATOR_URL,
        token,
        auth_account,
        force_manual=force_manual,
        no_submit=no_submit,
        region=region,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
