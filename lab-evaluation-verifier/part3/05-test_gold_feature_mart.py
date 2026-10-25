#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - gold_feature_mart
Verifies fraud_features_gold.gold_fraud_features Native Storage table metadata, clustering,
zero raw PII, customer-payment grain, active customer cardinality, and pre-aggregated dispute grand totals.
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
EVAL_NAME = "part3_gold_feature_mart"
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
        default_dataset="fraud_features_gold",
        script_file=__file__,
    )


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Queries Gold feature mart metadata, clustering, and grand total rollup metrics."""
    project_id, dataset, region = get_gcp_context()
    gold_dataset = "fraud_features_gold"
    gold_table = "gold_fraud_features"
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Checking Gold Feature Mart in {project_id}:{gold_dataset}.{gold_table}...")

    rc, meta, err = ec.run_bq_show_json(project_id, f"{project_id}:{gold_dataset}.{gold_table}")

    table_meta = {}
    grand_totals = {}
    if rc == 0 and meta:
        cols = [f.get("name") for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict)]
        clustering = meta.get("clustering", {}).get("fields", [])
        table_meta = {
            "exists": True,
            "type": meta.get("type", ""),
            "clustering_fields": clustering,
            "columns": cols,
            "no_raw_pii": ("ssn" not in cols) and ("email" not in cols),
            "raw_metadata": meta,
        }

        gold_sql = f"""
        SELECT
          COUNT(*) AS row_count,
          COUNT(DISTINCT customer_id) AS distinct_customers,
          SUM(total_tx_count) AS total_tx_count,
          FORMAT('%.2f', SUM(total_tx_amount)) AS total_tx_amount,
          FORMAT('%.2f', SUM(total_net_amount)) AS total_net_amount,
          SUM(high_risk_mcc_tx_count) AS high_risk_mcc_tx_count,
          FORMAT('%.2f', SUM(high_risk_mcc_amount)) AS high_risk_mcc_amount,
          SUM(ato_mfa_tx_count) AS ato_mfa_tx_count,
          FORMAT('%.2f', SUM(ato_mfa_tx_amount)) AS ato_mfa_tx_amount,
          SUM(disputed_tx_count) AS disputed_tx_count,
          FORMAT('%.2f', SUM(total_disputed_amount)) AS total_disputed_amount,
          FORMAT('%.2f', SUM(total_penalty_fee_usd)) AS total_penalty_fee_usd
        FROM `{project_id}.{gold_dataset}.{gold_table}`
        """
        grand_totals = run_bq_query(project_id, gold_sql, region=region)
    else:
        table_meta = {
            "exists": False,
            "error": err or "Table not found",
        }

    telemetry = {
        "project_id": project_id,
        "dataset": gold_dataset,
        "table": gold_table,
        "region": region,
        "table_meta": table_meta,
        "grand_totals": grand_totals,
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
        z.writestr("gold_feature_mart.json", json.dumps(telemetry, indent=2))

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
