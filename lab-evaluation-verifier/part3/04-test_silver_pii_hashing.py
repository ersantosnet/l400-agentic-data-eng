#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - silver_pii_hashing
Verifies plaintext PII removal (ssn, email), 64-char SHA-256 hex format (masked_ssn, masked_email),
and deterministic spot check for CUST-0000001 across customers_crm_silver and payment_transactions_silver.
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
EVAL_NAME = "part3_silver_pii_hashing"
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
run_bq_query = ec.run_bq_query_safe
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
    """Queries Silver PII hashing columns, regex match counts, and CUST-0000001 spot check."""
    project_id, dataset, region = get_gcp_context()
    dataset = "fraud_detection_db"
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Checking Silver SHA-256 PII hashing in {project_id}:{dataset}...")
    tables_info = {}

    for dom in ("customers_crm", "payment_transactions"):
        tbl = f"{dom}_silver"
        rc, meta, err = ec.run_bq_show_json(project_id, f"{project_id}:{dataset}.{tbl}")
        if rc != 0 or not meta:
            tables_info[tbl] = {
                "exists": False,
                "error": err or "Table not found",
            }
            continue

        cols = [f.get("name") for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict)]
        ssn_expr = "COUNTIF(REGEXP_CONTAINS(masked_ssn, r'^[0-9a-f]{64}$'))" if "masked_ssn" in cols else "-1"
        email_expr = "COUNTIF(REGEXP_CONTAINS(masked_email, r'^[0-9a-f]{64}$'))" if "masked_email" in cols else "-1"

        sql = f"""
        SELECT
          COUNT(*) AS total_rows,
          {ssn_expr} AS valid_ssn_cnt,
          {email_expr} AS valid_email_cnt
        FROM `{project_id}.{dataset}.{tbl}`
        """
        q_res = run_bq_query(project_id, sql, region=region)
        tables_info[tbl] = {
            "exists": True,
            "columns": cols,
            "plaintext_ssn_present": "ssn" in cols,
            "plaintext_email_present": "email" in cols,
            "hash_format_counts": q_res,
        }

    spot_check = {}
    crm_cols = tables_info.get("customers_crm_silver", {}).get("columns", [])
    if tables_info.get("customers_crm_silver", {}).get("exists") and "masked_ssn" in crm_cols:
        select_cols = "customer_id, masked_ssn, masked_email" if "masked_email" in crm_cols else "customer_id, masked_ssn"
        spot_sql = f"SELECT {select_cols} FROM `{project_id}.{dataset}.customers_crm_silver` WHERE customer_id = 'CUST-0000001' LIMIT 1"
        spot_check = run_bq_query(project_id, spot_sql, region=region)
        rows = spot_check if isinstance(spot_check, list) else (spot_check.get("rows", []) if isinstance(spot_check, dict) else [])
        if rows and isinstance(rows[0], dict):
            row0 = rows[0]
            expected_ssn = "97bf84018efb0f9a1a7d46f5b215c8c4c5611b2058b67e36261a4c9b33eb14ab"
            expected_email = "61325dd137c74ee3192c9bbb00c295918e3e341d9448797a283ebfd54c7cf365"
            ssn_ok = row0.get("masked_ssn") == expected_ssn
            email_ok = row0.get("masked_email") == expected_email
            print(
                f"  [P4.2/P4.3 Spot Check] CUST-0000001 masked_ssn={'PASS' if ssn_ok else 'MISMATCH'}, "
                f"masked_email={'PASS' if email_ok else 'MISMATCH'}"
            )

    telemetry = {
        "project_id": project_id,
        "dataset": dataset,
        "region": region,
        "tables": tables_info,
        "cust_0000001_spot_check": spot_check,
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
        z.writestr("silver_pii_hashing.json", json.dumps(telemetry, indent=2))

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
