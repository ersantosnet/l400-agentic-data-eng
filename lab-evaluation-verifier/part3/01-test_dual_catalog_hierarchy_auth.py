#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - dual_catalog_hierarchy_auth
Gathers BigQuery Connection (lakehouse-vending-conn) and Dual BigLake Iceberg REST Catalog (acme_bronze_dev & acme_silver_dev) state.
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
EVAL_NAME = "part3_dual_catalog_hierarchy_auth"
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
submit_bundle = ec.submit_bundle
print_manual_instructions = ec.print_manual_instructions


def get_gcp_context() -> tuple[str, str, str]:
    """Reads project, dataset, and region configurations via _eval_common.resolve_gcp_context."""
    return ec.resolve_gcp_context(part_num=3, script_file=__file__)


def api_get(url: str, access_token: str, project_id: str) -> tuple[int, dict]:
    """Performs an authenticated GET request against Google Cloud REST APIs."""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "x-goog-user-project": project_id,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, safe_json_loads(raw, {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, safe_json_loads(raw, {"raw_error": raw})
    except Exception as e:
        return 500, {"raw_error": str(e)}


def create_bundle(output_zip_path: str, student_account: str, student_ldap: str):
    """Queries BigQuery Connection and BigLake Iceberg REST Catalogs for Phase 1."""
    project_id, _, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    env_sfx = os.environ.get("ENV", "dev").lower()
    access_token = get_access_token()

    print(f"Fetching BigQuery Connection and BigLake Iceberg REST Catalogs for project: {project_id} ({region})...")
    conn_code, conn_resp = api_get(
        f"https://bigqueryconnection.googleapis.com/v1/projects/{project_id}/locations/{region}/connections/lakehouse-vending-conn",
        access_token,
        project_id,
    )

    cat_code, cat_resp = api_get(
        f"https://biglake.googleapis.com/iceberg/v1beta/restcatalog/extensions/projects/{project_id}/catalogs",
        access_token,
        project_id,
    )

    catalog_configs = {}
    for tier in ("bronze", "silver"):
        cat_id = f"acme_{tier}_{env_sfx}"
        cfg_code, cfg_resp = api_get(
            f"https://biglake.googleapis.com/iceberg/v1/restcatalog/v1/config?warehouse=bl://projects/{project_id}/catalogs/{cat_id}",
            access_token,
            project_id,
        )
        catalog_configs[cat_id] = {
            "http_status": cfg_code,
            "config": cfg_resp,
        }

    telemetry = {
        "project_id": project_id,
        "region": region,
        "environment": env_sfx,
        "bigquery_connection": {
            "connection_id": "lakehouse-vending-conn",
            "http_status": conn_code,
            "response": conn_resp,
        },
        "biglake_iceberg_catalogs": {
            "http_status": cat_code,
            "response": cat_resp,
        },
        "iceberg_rest_configs": catalog_configs,
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
        z.writestr("dual_catalog_hierarchy_auth.json", json.dumps(telemetry, indent=2))

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
