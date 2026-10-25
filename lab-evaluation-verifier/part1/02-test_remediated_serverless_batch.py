#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part1 - remediated_serverless_batch
Fetches Dataproc Serverless batch execution telemetry for orders_enrichment_fixed.py.
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
EVAL_NAME = "part1_remediated_serverless_batch"
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
    return ec.resolve_gcp_context(part_num=1, script_file=__file__)


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Fetches Dataproc Serverless batches and filters remediated batch telemetry."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Fetching Dataproc Serverless batches in {region} for project: {project_id}...")
    p = subprocess.run(
        ["gcloud", "dataproc", "batches", "list", f"--project={project_id}", f"--region={region}", "--format=json"],
        capture_output=True,
        text=True,
        timeout=45,
        stdin=subprocess.DEVNULL,
        env=ec.build_gcp_subprocess_env(),
    )

    all_batches = safe_json_loads(p.stdout, []) if (p.returncode == 0 and p.stdout.strip()) else []
    remediated_batches = []
    if isinstance(all_batches, list):
        for b in all_batches:
            if not isinstance(b, dict):
                continue
            pyspark_batch = b.get("pysparkBatch") or {}
            main_file = pyspark_batch.get("mainPythonFileUri", "")
            batch_name = b.get("name", "")
            if "orders_enrichment_fixed.py" in main_file or "remediated" in batch_name or "fixed" in batch_name:
                remediated_batches.append(b)

    payload = {
        "project_id": project_id,
        "region": region,
        "batches_count": len(all_batches) if isinstance(all_batches, list) else 0,
        "remediated_batches_count": len(remediated_batches),
        "remediated_batches": remediated_batches,
        "all_batches": all_batches,
        "error": p.stderr.strip() if p.returncode != 0 else None,
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
        z.writestr("dataproc_batches.json", json.dumps(all_batches, indent=2))
        z.writestr("remediated_batches.json", json.dumps(payload, indent=2))

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
