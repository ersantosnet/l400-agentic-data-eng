#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - orchestration_dq_lineage (Phase 7c)
Verifies staged Cloud Composer 3 DAG (medallion_lakehouse_dag.py),
Dataplex Auto Data Quality scan (fraud-gold-dq-scan-dev),
and OpenLineage / Dataplex Data Lineage processes across regional and multi-regional endpoints.
Supports both Automatic submission (local proxy / Cloud Run validator) and Manual submission (web upload).
"""

import os
import sys
import json
import zipfile
import subprocess
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec

LAB = "L400-agentic-data-eng"
EVAL_NAME = "part3_orchestration_dq_lineage"
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
get_access_token = ec.get_access_token_safe
api_get = ec.gcp_api_get
submit_bundle = ec.submit_bundle
print_manual_instructions = ec.print_manual_instructions


def get_gcp_context() -> tuple[str, str, str]:
    """Reads project, dataset, and region configurations via _eval_common.resolve_gcp_context."""
    return ec.resolve_gcp_context(
        part_num=3,
        default_dataset="fraud_detection_db",
        script_file=__file__,
    )


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Collects Composer DAG, Dataplex Auto DQ Scans, and OpenLineage processes."""
    project_id, dataset, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    access_token = get_access_token()
    warehouse_bucket = f"gs://{project_id}-lakehouse-warehouse"
    dag_gcs_uri = f"{warehouse_bucket}/dags/medallion_lakehouse_dag.py"

    print(f"Checking Composer DAG, Dataplex Auto DQ Scans, and Data Lineage in {project_id}...")

    # 1. Staged Composer DAG
    dag_ls = subprocess.run(
        ["gcloud", "storage", "ls", dag_gcs_uri, f"--project={project_id}"],
        capture_output=True,
        text=True,
        timeout=45,
        stdin=subprocess.DEVNULL,
        env=ec.build_gcp_subprocess_env(),
    )
    dag_staged_in_gcs = dag_ls.returncode == 0
    dag_content = ""
    if dag_staged_in_gcs:
        cat_proc = subprocess.run(
            ["gcloud", "storage", "cat", dag_gcs_uri, f"--project={project_id}"],
            capture_output=True,
            text=True,
            timeout=45,
            stdin=subprocess.DEVNULL,
            env=ec.build_gcp_subprocess_env(),
        )
        if cat_proc.returncode == 0:
            dag_content = cat_proc.stdout
    if not dag_content and not ec.is_strict_gcs_only():
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        for local_cand in (
            "src/part3/dags/medallion_lakehouse_dag.py",
            "../src/part3/dags/medallion_lakehouse_dag.py",
            "../../src/part3/dags/medallion_lakehouse_dag.py",
            os.path.join(repo_root, "src/part3/dags/medallion_lakehouse_dag.py"),
            "dags/medallion_lakehouse_dag.py",
            "scripts/medallion_lakehouse_dag.py",
            "../../dags/medallion_lakehouse_dag.py",
            "../../scripts/medallion_lakehouse_dag.py",
            "../../lab-packs/part3/solution/medallion_lakehouse_dag.py",
            "../../lab-packs/part3-medallion-solution/dags/medallion_lakehouse_dag.py",
        ):
            if os.path.exists(local_cand):
                try:
                    with open(local_cand, "r", encoding="utf-8") as f:
                        dag_content = f.read()
                    break
                except Exception:
                    pass

    # 2. Dataplex Auto Data Quality Scans
    scans_code, scans_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/dataScans",
        access_token,
        project_id,
    )

    # 3. Data Lineage Processes (poll regional + continent multi-regional location)
    lineage_processes = {}
    multi_loc = "eu" if region.startswith("europe-") else "us"
    for loc in dict.fromkeys([region, multi_loc, "us"]):
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
        "signature": signature,
    }

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest_data, indent=2))
        z.writestr("orchestration_dq_lineage.json", json.dumps(telemetry, indent=2))
        if dag_content:
            z.writestr("medallion_lakehouse_dag.py", dag_content)

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
