#!/usr/bin/env python3
"""
Lab Evaluation: L400-da-data-engineering-part3 - knowledge_catalog_data_mesh (Phase 7b)
Verifies Knowledge Catalog Pattern 2 Data Mesh hierarchy:
  - Top-level Data Domain `FraudDomain` (`fraud-domain`)
  - 3 Child Sub-Domains: `Fraud/Bronze` (`fraud-bronze`), `Fraud/Silver` (`fraud-silver`), `Fraud/Gold` (`fraud-gold`)
  - 11 BigQuery Table Resource Bindings (5 Bronze -> Fraud/Bronze, 5 Silver -> Fraud/Silver, 1 Gold -> Fraud/Gold)
  - Data Product `FraudRiskFeatureStore` with attached `gold_fraud_features` Data Asset
  - Advisory Data Product binding on `FraudDomain` & informational Dataplex Lakes
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
EVAL_NAME = "part3_knowledge_catalog_data_mesh"
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
    """Collects Knowledge Catalog Data Domains, Sub-Domains, Resource Bindings, Data Products, Assets, and Lakes."""
    project_id, dataset, region = get_gcp_context()
    if not project_id:
        print("Error: Could not determine PROJECT_ID.")
        sys.exit(1)

    access_token = get_access_token()
    print(f"Checking Knowledge Catalog Data Mesh (Domains, Sub-Domains, Resource Bindings & Data Products) in {project_id}...")

    lakes_code, lakes_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/lakes",
        access_token,
        project_id,
    )
    domains_code, domains_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/dataDomains",
        access_token,
        project_id,
    )

    domain_bindings: dict[str, dict] = {}
    bindings_by_domain: dict[str, dict] = {}
    domain_list = domains_resp.get("dataDomains", []) if isinstance(domains_resp, dict) else []
    for dom_obj in domain_list:
        if not isinstance(dom_obj, dict):
            continue
        dom_full_name = str(dom_obj.get("name") or "").strip()
        if not dom_full_name:
            continue
        dom_short_id = dom_full_name.split("/")[-1]
        b_code, b_resp = api_get(
            f"https://dataplex.googleapis.com/v1/{dom_full_name}/bindings",
            access_token,
            project_id,
        )
        raw_bindings = b_resp.get("dataDomainBindings", []) if isinstance(b_resp, dict) else []
        bound_resources = [
            str(b.get("resource") or "").strip()
            for b in raw_bindings
            if isinstance(b, dict) and str(b.get("resource") or "").strip()
        ]
        bound_tables = [r for r in bound_resources if "bigquery.googleapis.com/" in r and "/tables/" in r]
        bound_data_products = [r for r in bound_resources if "/dataProducts/" in r]

        domain_bindings[dom_short_id] = {
            "domain_name": dom_full_name,
            "display_name": dom_obj.get("displayName", ""),
            "parent_data_domain": dom_obj.get("parentDataDomain", ""),
            "status_code": b_code,
            "response": b_resp,
        }
        bindings_by_domain[dom_short_id] = {
            "domain_name": dom_full_name,
            "display_name": dom_obj.get("displayName", ""),
            "parent_data_domain": dom_obj.get("parentDataDomain", ""),
            "bound_resources": bound_resources,
            "bound_tables": bound_tables,
            "bound_data_products": bound_data_products,
            "table_binding_count": len(bound_tables),
        }

    dp_code, dp_resp = api_get(
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{region}/dataProducts",
        access_token,
        project_id,
    )
    data_product_assets: dict[str, dict] = {}
    dp_list = dp_resp.get("dataProducts", []) if isinstance(dp_resp, dict) else []
    for dp_obj in dp_list:
        if not isinstance(dp_obj, dict):
            continue
        dp_full_name = str(dp_obj.get("name") or "").strip()
        if not dp_full_name:
            continue
        dp_short_id = dp_full_name.split("/")[-1]
        da_code, da_resp = api_get(
            f"https://dataplex.googleapis.com/v1/{dp_full_name}/dataAssets",
            access_token,
            project_id,
        )
        data_product_assets[dp_short_id] = {
            "data_product_name": dp_full_name,
            "display_name": dp_obj.get("displayName", ""),
            "status_code": da_code,
            "response": da_resp,
        }

    telemetry = {
        "project_id": project_id,
        "region": region,
        "dataplex_lakes": {
            "status_code": lakes_code,
            "response": lakes_resp,
        },
        "dataplex_data_domains": {
            "status_code": domains_code,
            "response": domains_resp,
        },
        "dataplex_domain_bindings": domain_bindings,
        "bindings_by_domain": bindings_by_domain,
        "dataplex_data_products": {
            "status_code": dp_code,
            "response": dp_resp,
        },
        "dataplex_data_product_assets": data_product_assets,
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
        z.writestr("knowledge_catalog_data_mesh.json", json.dumps(telemetry, indent=2))

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
