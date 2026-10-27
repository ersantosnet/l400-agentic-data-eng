#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - security_metadata_governance (Phase 7a)
Verifies column-level Policy Tags (SSN_Cardholder) on Bronze ssn columns,
Dataplex Knowledge Catalog Aspect Type (medallion-governance-template),
and Gold table (@bigquery entry) governance aspect attachment.
Supports both Automatic submission (local proxy / Cloud Run validator) and Manual submission (web upload).
"""

import os
import sys
import json
import zipfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec

LAB = "L400-agentic-data-eng"
EVAL_NAME = "part3_security_metadata_governance"
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
    """Collects Bronze Policy Tag metadata, Dataplex KC Aspect Type, and Gold @bigquery Entry aspects."""
    project_id, dataset, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    access_token = get_access_token()
    print(f"Checking Bronze Policy Tags, Knowledge Catalog Aspect Type, and Gold Entry Aspects in {project_id}...")

    # 1. Bronze Policy Tags on ssn columns
    bronze_policy_tags = {}
    for tbl in ("customers_crm_bronze", "payment_transactions_bronze"):
        rc, meta, err_msg = ec.run_bq_show_json(project_id, f"{project_id}:fraud_detection_db.{tbl}")
        if rc == 0 and meta:
            ssn_field = next(
                (f for f in meta.get("schema", {}).get("fields", []) if isinstance(f, dict) and f.get("name") == "ssn"),
                {},
            )
            ptags = ssn_field.get("policyTags", {}).get("names", []) if isinstance(ssn_field, dict) else []
            bronze_policy_tags[tbl] = {
                "exists": True,
                "ssn_policy_tags": ptags,
                "has_policy_tag": len(ptags) > 0,
            }
        else:
            bronze_policy_tags[tbl] = {
                "exists": False,
                "ssn_policy_tags": [],
                "has_policy_tag": False,
                "error": err_msg or "Table not found",
            }

    # 2. Dataplex Knowledge Catalog Aspect Type & Gold Entry Aspects
    asp_code, asp_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/aspectTypes/medallion-governance-template",
        access_token,
        project_id,
    )
    ent_code, gold_ent = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/entryGroups/@bigquery/entries/"
        f"bigquery.googleapis.com/projects/{project_id}/datasets/fraud_features_gold/tables/gold_fraud_features?view=ALL",
        access_token,
        project_id,
    )

    telemetry = {
        "project_id": project_id,
        "region": region,
        "bronze_policy_tags": bronze_policy_tags,
        "aspect_type": {
            "status_code": asp_code,
            "response": asp_resp,
        },
        "gold_dataplex_entry": {
            "status_code": ent_code,
            "response": gold_ent,
        },
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
        z.writestr("security_metadata_governance.json", json.dumps(telemetry, indent=2))

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
