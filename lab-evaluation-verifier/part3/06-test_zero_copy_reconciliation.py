#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - zero_copy_reconciliation
Verifies 100% penny-exact zero-copy reconciliation across payment_method IN (0, 1, 2)
between BigLake Iceberg Silver tables and BigQuery Native Storage Gold feature mart.
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
EVAL_NAME = "part3_zero_copy_reconciliation"
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
    """Runs the cross-engine Silver-to-Gold reconciliation query by payment_method."""
    project_id, dataset, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Running Zero-Copy Silver-to-Gold reconciliation query in {project_id}...")
    rec_sql = f"""
    WITH silver_disputes_by_tx AS (
      SELECT
        transaction_id,
        COUNT(dispute_id) AS dispute_count,
        ROUND(SUM(dispute_amount), 2) AS disputed_amount,
        ROUND(SUM(penalty_fee_usd), 2) AS penalty_fee_usd
      FROM `{project_id}.fraud_detection_db.chargeback_disputes_silver`
      GROUP BY transaction_id
    ),
    silver_agg AS (
      SELECT
        t.payment_method,
        COUNT(t.transaction_id) AS silver_tx_count,
        ROUND(SUM(t.tx_amount), 2) AS silver_gross_usd,
        ROUND(SUM(t.net_amount_after_discount), 2) AS silver_net_usd,
        SUM(COALESCE(d.dispute_count, 0)) AS silver_dispute_count,
        ROUND(SUM(COALESCE(d.disputed_amount, NUMERIC '0.00')), 2) AS silver_disputed_usd
      FROM `{project_id}.fraud_detection_db.payment_transactions_silver` t
      LEFT JOIN silver_disputes_by_tx d
        ON t.transaction_id = d.transaction_id
      GROUP BY t.payment_method
    ),
    gold_agg AS (
      SELECT
        payment_method,
        SUM(total_tx_count) AS gold_tx_count,
        ROUND(SUM(total_tx_amount), 2) AS gold_gross_usd,
        ROUND(SUM(total_net_amount), 2) AS gold_net_usd,
        SUM(disputed_tx_count) AS gold_dispute_count,
        ROUND(SUM(total_disputed_amount), 2) AS gold_disputed_usd
      FROM `{project_id}.fraud_features_gold.gold_fraud_features`
      GROUP BY payment_method
    )
    SELECT
      s.payment_method,
      s.silver_tx_count,
      g.gold_tx_count,
      (s.silver_tx_count - g.gold_tx_count) AS row_count_diff,
      FORMAT('%.2f', s.silver_gross_usd) AS silver_gross_usd,
      FORMAT('%.2f', g.gold_gross_usd) AS gold_gross_usd,
      FORMAT('%.2f', s.silver_gross_usd - g.gold_gross_usd) AS gross_variance_usd,
      FORMAT('%.2f', s.silver_net_usd) AS silver_net_usd,
      FORMAT('%.2f', g.gold_net_usd) AS gold_net_usd,
      FORMAT('%.2f', s.silver_net_usd - g.gold_net_usd) AS net_variance_usd,
      FORMAT('%.2f', s.silver_disputed_usd) AS silver_disputed_usd,
      FORMAT('%.2f', g.gold_disputed_usd) AS gold_disputed_usd,
      FORMAT('%.2f', s.silver_disputed_usd - g.gold_disputed_usd) AS disputed_variance_usd
    FROM silver_agg s
    INNER JOIN gold_agg g USING (payment_method)
    ORDER BY s.payment_method
    """
    reconciliation_rows = run_bq_query(project_id, rec_sql, region=region)

    telemetry = {
        "project_id": project_id,
        "region": region,
        "reconciliation_rows": reconciliation_rows,
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
        z.writestr("zero_copy_reconciliation.json", json.dumps(telemetry, indent=2))

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
