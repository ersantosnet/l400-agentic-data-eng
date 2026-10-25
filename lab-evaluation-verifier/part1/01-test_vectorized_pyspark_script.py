#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part1 - vectorized_pyspark_script
Gathers the refactored vectorized PySpark script (orders_enrichment_fixed.py) from GCS or local workspace.
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
EVAL_NAME = "part1_vectorized_pyspark_script"
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
    """Fetches orders_enrichment_fixed.py from GCS or local workspace and bundles it."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    gcs_uri = f"gs://{project_id}-lakehouse-warehouse/scripts/orders_enrichment_fixed.py"
    print(f"Gathering vectorized PySpark script from {gcs_uri} (project: {project_id})...")

    p = subprocess.run(
        ["gcloud", "storage", "cat", gcs_uri, f"--project={project_id}"],
        capture_output=True,
        text=True,
        timeout=45,
        stdin=subprocess.DEVNULL,
        env=ec.build_gcp_subprocess_env(),
    )
    script_content = ""
    source_location = ""

    if p.returncode == 0 and p.stdout.strip():
        script_content = p.stdout
        source_location = gcs_uri
    elif not ec.is_strict_gcs_only():
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        for local_candidate in (
            "src/part1/orders_enrichment_fixed.py",
            "../src/part1/orders_enrichment_fixed.py",
            "../../src/part1/orders_enrichment_fixed.py",
            os.path.join(repo_root, "src/part1/orders_enrichment_fixed.py"),
            "scripts/orders_enrichment_fixed.py",
            "../scripts/orders_enrichment_fixed.py",
            "../../scripts/orders_enrichment_fixed.py",
            os.path.join(repo_root, "scripts/orders_enrichment_fixed.py"),
        ):
            if os.path.isfile(local_candidate):
                with open(local_candidate, "r", encoding="utf-8") as f:
                    script_content = f.read()
                source_location = local_candidate
                break

    metadata = {
        "project_id": project_id,
        "region": region,
        "expected_gcs_uri": gcs_uri,
        "found": bool(script_content.strip()),
        "source_location": source_location or None,
        "gcs_error": p.stderr.strip() if p.returncode != 0 else None,
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
        z.writestr("script_source_metadata.json", json.dumps(metadata, indent=2))
        if script_content:
            z.writestr("orders_enrichment_fixed.py", script_content)
            z.writestr("scripts/orders_enrichment_fixed.py", script_content)

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
