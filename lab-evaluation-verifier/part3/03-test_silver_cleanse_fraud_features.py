#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - silver_cleanse_fraud_features
Queries the 5 Silver Iceberg V2 tables in fraud_detection_db for row counts, Class N4 benign nulls,
golden primary/secondary sums, Haversine distance/velocity features, and DEV-FRAUD-999 fraud ring count.
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
EVAL_NAME = "part3_silver_cleanse_fraud_features"
ZIP_FILENAME = f"{EVAL_NAME}.zip"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app")
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")

SILVER_TABLE_SPECS = {
    "customers_crm": {
        "primary_col": "credit_limit_usd",
        "secondary_col": "reward_points",
        "secondary_is_int": True,
        "n4_expr": "phone IS NULL OR loyalty_tier IS NULL",
    },
    "merchants_stores": {
        "primary_col": "terminal_monthly_fee_usd",
        "secondary_col": "commission_rate_pct",
        "secondary_is_int": False,
        "n4_expr": "store_manager_code IS NULL OR region_notes IS NULL",
    },
    "device_auth_logs": {
        "primary_col": "auth_latency_ms",
        "secondary_col": "risk_score_raw",
        "secondary_is_int": False,
        "n4_expr": "user_agent IS NULL OR mfa_method IS NULL",
    },
    "payment_transactions": {
        "primary_col": "tx_amount",
        "secondary_col": "net_amount_after_discount",
        "secondary_is_int": False,
        "n4_expr": "device_ip IS NULL OR promo_code IS NULL",
    },
    "chargeback_disputes": {
        "primary_col": "dispute_amount",
        "secondary_col": "penalty_fee_usd",
        "secondary_is_int": False,
        "n4_expr": "customer_statement IS NULL OR agent_notes IS NULL",
    },
}

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


def check_latest_batch_runtime_advisory(project_id: str, region: str, stage_label: str) -> dict:
    """Advisory check that the latest succeeded Dataproc Serverless batch uses Premium + Lightning Engine + native."""
    try:
        proc = subprocess.run(
            [
                "gcloud", "dataproc", "batches", "list",
                f"--project={project_id}",
                f"--region={region}",
                "--filter=state=SUCCEEDED",
                "--sort-by=~createTime",
                "--limit=10",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            env=ec.build_gcp_subprocess_env(),
        )
        batches = safe_json_loads(proc.stdout, [])
        if not isinstance(batches, list) or not batches:
            msg = "No SUCCEEDED Dataproc Serverless batch found (advisory check skipped)."
            print(f"  [ADVISORY] {stage_label} Runtime Conformance: {msg}")
            return {"checked": False, "message": msg}

        stage_key = stage_label.lower()
        latest = next(
            (b for b in batches if stage_key in b.get("name", "").lower()),
            batches[0],
        )
        batch_name = latest.get("name", "").split("/")[-1]
        props = {}
        props.update(latest.get("runtimeConfig", {}).get("properties", {}) or {})
        props.update(latest.get("runtimeInfo", {}).get("properties", {}) or {})

        tier = props.get("dataproc:dataproc.tier") or props.get("dataproc.tier") or ""
        engine = props.get("spark:spark.dataproc.engine") or props.get("spark.dataproc.engine") or ""
        le_runtime = (
            props.get("spark:spark.dataproc.lightningEngine.runtime")
            or props.get("spark.dataproc.lightningEngine.runtime")
            or ""
        )
        conforms = (
            tier == "premium"
            and engine == "lightningEngine"
            and le_runtime == "native"
        )
        status_tag = "PASS" if conforms else "WARN"
        print(
            f"  [ADVISORY:{status_tag}] {stage_label} Batch '{batch_name}': "
            f"tier={tier or 'unset'}, engine={engine or 'unset'}, runtime={le_runtime or 'unset'}"
        )
        return {
            "checked": True,
            "batch_id": batch_name,
            "tier": tier,
            "engine": engine,
            "lightning_engine_runtime": le_runtime,
            "conforms": conforms,
        }
    except Exception as exc:
        print(f"  [ADVISORY] {stage_label} Runtime Conformance check warning: {exc}")
        return {"checked": False, "error": str(exc)}


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Queries all 5 Silver tables for row counts, N4 nulls, primary/secondary sums, and fraud features."""
    project_id, dataset, region = get_gcp_context()
    dataset = "fraud_detection_db"
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    print(f"Querying 5 Silver tables in {project_id}:{dataset}...")
    silver_results = {}

    for dom, spec in SILVER_TABLE_SPECS.items():
        tbl = f"{dom}_silver"
        rc, meta, err = ec.run_bq_show_json(project_id, f"{project_id}:{dataset}.{tbl}")
        if rc != 0 or not meta:
            silver_results[tbl] = {
                "exists": False,
                "error": err or "Table not found",
            }
            continue

        cols = [f.get("name") for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict)]
        p_col = spec["primary_col"]
        s_col = spec["secondary_col"]
        s_fmt = f"CAST(SUM({s_col}) AS STRING)" if spec["secondary_is_int"] else f"FORMAT('%.2f', SUM({s_col}))"
        n4_expr = spec["n4_expr"]

        extra_selects = []
        if dom == "payment_transactions" and "geo_distance_km" in cols and "velocity_1h" in cols:
            extra_selects.append("COUNTIF(geo_distance_km IS NOT NULL AND velocity_1h >= 1) AS feat_cnt")
            extra_selects.append("COUNTIF(velocity_1h >= 5 OR geo_distance_km > 500.0) AS anomaly_cnt")
            extra_selects.append("COUNT(DISTINCT IF(device_id = 'DEV-FRAUD-999', customer_id, NULL)) AS ring_cnt")
        else:
            extra_selects.append("-1 AS feat_cnt, -1 AS anomaly_cnt, -1 AS ring_cnt")

        sql = f"""
        SELECT
          COUNT(*) AS cnt,
          COUNTIF({n4_expr}) AS n4_cnt,
          FORMAT('%.2f', SUM({p_col})) AS p_sum,
          {s_fmt} AS s_sum,
          {", ".join(extra_selects)}
        FROM `{project_id}.{dataset}.{tbl}`
        """
        q_res = run_bq_query(project_id, sql, region=region)
        silver_results[tbl] = {
            "exists": True,
            "columns": cols,
            "table_metadata": meta,
            "metrics": q_res,
        }

    runtime_advisory = check_latest_batch_runtime_advisory(project_id, region, "Silver")

    telemetry = {
        "project_id": project_id,
        "dataset": dataset,
        "region": region,
        "silver_tables": silver_results,
        "runtime_conformance_advisory": runtime_advisory,
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
        z.writestr("silver_cleanse_fraud_features.json", json.dumps(telemetry, indent=2))

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
