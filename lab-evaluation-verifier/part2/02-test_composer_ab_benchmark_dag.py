#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part2 - composer_ab_benchmark_dag
Gathers the Cloud Composer 3 A/B Benchmark DAG (nqe_benchmark_dag.py) from GCS or local workspace.
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
EVAL_NAME = "part2_composer_ab_benchmark_dag"
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
    """Fetches nqe_benchmark_dag.py from GCS or local directories and bundles it."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Gathering Cloud Composer 3 A/B Benchmark DAG (nqe_benchmark_dag.py) for project: {project_id}...")
    gcs_candidates = [
        f"gs://{project_id}-lakehouse-warehouse/scripts/nqe_benchmark_dag.py",
        f"gs://{project_id}-lakehouse-warehouse/dags/nqe_benchmark_dag.py",
    ]

    dag_code = ""
    source_uri = ""
    for gcs_uri in gcs_candidates:
        p = subprocess.run(
            ["gcloud", "storage", "cat", gcs_uri, f"--project={project_id}"],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            env=ec.build_gcp_subprocess_env(),
        )
        if p.returncode == 0 and p.stdout.strip():
            dag_code = p.stdout
            source_uri = gcs_uri
            break

    if not dag_code and not ec.is_strict_gcs_only():
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        local_candidates = [
            "src/part2/dags/nqe_benchmark_dag.py",
            "../src/part2/dags/nqe_benchmark_dag.py",
            "../../src/part2/dags/nqe_benchmark_dag.py",
            os.path.join(repo_root, "src/part2/dags/nqe_benchmark_dag.py"),
            "dags/nqe_benchmark_dag.py",
            "scripts/nqe_benchmark_dag.py",
            "../dags/nqe_benchmark_dag.py",
            "../scripts/nqe_benchmark_dag.py",
            "../../dags/nqe_benchmark_dag.py",
            "../../scripts/nqe_benchmark_dag.py",
            os.path.join(repo_root, "dags/nqe_benchmark_dag.py"),
            os.path.join(repo_root, "scripts/nqe_benchmark_dag.py"),
        ]
        for lc in local_candidates:
            if os.path.isfile(lc):
                with open(lc, "r", encoding="utf-8") as f:
                    dag_code = f.read()
                source_uri = lc
                break

    dag_meta = {
        "project_id": project_id,
        "region": region,
        "found": bool(dag_code.strip()),
        "source_uri": source_uri or None,
        "gcs_candidates_checked": gcs_candidates,
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
        z.writestr("dag_metadata.json", json.dumps(dag_meta, indent=2))
        if dag_code:
            z.writestr("nqe_benchmark_dag.py", dag_code)
            z.writestr("dags/nqe_benchmark_dag.py", dag_code)

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
