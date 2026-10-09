#!/usr/bin/env python3
"""
ACME Global Payment Fraud Lakehouse - Data Mesh Governance & Privacy Enforcement
Step 05 Production Script: apply_kc_governance.py

Business Objective:
Implements Dataplex Knowledge Catalog Pattern 2:
1. Registers Data Domain 'FraudDomain' and Data Product 'FraudRiskFeatureStore'.
2. Defines AspectType 'medallion-governance-template' and attaches aspect card to all 11 BigQuery entries
   (5 Bronze with ssn_masked=False, 5 Silver and 1 Gold with ssn_masked=True).
3. Attaches Policy Tag 'SSN_Cardholder' and configures BigQuery SHA256 Dynamic Data Masking
   on Bronze SSN columns (customers_crm_bronze.ssn, payment_transactions_bronze.ssn).

Adheres strictly to .ai-rules/agent_skills_standards.md:
- Uses urllib.request and gcloud access token for standard library REST calls.
- Dynamically loads environment parameters from agent-config.json.
"""

import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("acme_kc_governance")


def load_config() -> Dict[str, str]:
    """Load configuration from agent-config.json or environment variables."""
    config: Dict[str, str] = {}
    config_file = "agent-config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            logger.info("Loaded runtime configuration from %s", config_file)
        except Exception as e:
            logger.warning("Could not read %s: %s", config_file, e)

    return {
        "project_id": config.get("gcp-project-id", os.environ.get("PROJECT_ID", "acme-l400-part3-eri-01")),
        "location": config.get("primary-region", os.environ.get("REGION", "us-central1")),
        "env": config.get("env", os.environ.get("ENV", "dev")),
        "domain_id": config.get("knowledge-catalog-domain", "FraudDomain"),
        "product_id": config.get("knowledge-catalog-data-product", "FraudRiskFeatureStore"),
        "aspect_id": config.get("knowledge-catalog-aspect", "medallion-governance-template"),
        "lakehouse_dataset": config.get("bigquery-lakehouse-dataset", "fraud_detection_db"),
        "gold_dataset": config.get("bigquery-gold-dataset", "fraud_features_gold"),
    }


class RestResponse:
    """Wrapper matching standard response interface."""

    def __init__(self, status_code: int, data: bytes):
        self.status_code = status_code
        self.data = data

    def json(self) -> Any:
        if not self.data:
            return {}
        try:
            return json.loads(self.data.decode("utf-8"))
        except Exception:
            return {}

    @property
    def text(self) -> str:
        return self.data.decode("utf-8") if self.data else ""


class GCPRestClient:
    """Lightweight REST API client using urllib.request and gcloud access token."""

    def __init__(self, project_id: str, location: str):
        self.project_id = project_id
        self.location = location

    def _get_token(self) -> str:
        try:
            out = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True)
            return out.strip()
        except Exception as e:
            logger.warning("Could not get gcloud token: %s", e)
            return ""

    def get_project_number(self) -> str:
        try:
            out = subprocess.check_output(
                ["gcloud", "projects", "describe", self.project_id, "--format=value(projectNumber)"],
                text=True
            )
            return out.strip()
        except Exception as e:
            logger.warning("Could not get project number: %s", e)
            return ""

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> RestResponse:
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": self.project_id,
        }

        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return RestResponse(resp.status, resp.read())
        except urllib.error.HTTPError as e:
            return RestResponse(e.code, e.read())
        except Exception as e:
            logger.error("Request failed: %s", e)
            return RestResponse(500, b"")

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> RestResponse:
        return self._request("GET", url, params=params)

    def post(self, url: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> RestResponse:
        return self._request("POST", url, data=data, params=params)

    def patch(self, url: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> RestResponse:
        return self._request("PATCH", url, data=data, params=params)

    def put(self, url: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> RestResponse:
        return self._request("PUT", url, data=data, params=params)


def ensure_dataplex_domain(client: GCPRestClient, conf: Dict[str, str]) -> None:
    """Ensure Dataplex Data Domain exists."""
    project = conf["project_id"]
    location = conf["location"]
    domain_id = conf["domain_id"].lower()
    url = f"https://dataplex.googleapis.com/v1/projects/{project}/locations/{location}/dataDomains"

    check_url = f"{url}/{domain_id}"
    resp = client.get(check_url)
    if resp.status_code == 200:
        logger.info("Dataplex Data Domain '%s' already exists.", domain_id)
        return

    payload = {
        "displayName": conf["domain_id"],
        "description": "Enterprise Fraud Prevention Lakehouse Domain for ACME Global Payments",
        "contacts": {
            "identities": [
                {
                    "contactName": "Fraud Operations",
                    "contactRole": "OWNER",
                    "contactId": f"sa-dataproc-serverless@{project}.iam.gserviceaccount.com",
                }
            ]
        },
        "labels": {
            "env": conf["env"],
            "cost_center": "fraud_prevention",
            "workload": "fraud_lakehouse",
        },
    }
    create_resp = client.post(url, payload, params={"dataDomainId": domain_id})
    if create_resp.status_code in (200, 201):
        logger.info("Successfully provisioned Dataplex Data Domain: %s", domain_id)
    else:
        logger.warning(
            "Data domain check/creation returned %d: %s",
            create_resp.status_code, create_resp.text
        )


def ensure_data_product(client: GCPRestClient, conf: Dict[str, str]) -> None:
    """Ensure Data Product 'FraudRiskFeatureStore' exists in Dataplex."""
    project = conf["project_id"]
    location = conf["location"]
    product_id = conf["product_id"].lower()
    url = f"https://dataplex.googleapis.com/v1/projects/{project}/locations/{location}/dataProducts"

    check_url = f"{url}/{product_id}"
    resp = client.get(check_url)
    if resp.status_code == 200:
        logger.info("Dataplex Data Product '%s' already exists.", product_id)
        return

    payload = {
        "displayName": conf["product_id"],
        "description": "Certified Behavioral Fraud Risk Feature Store with Hourly Freshness SLA",
        "ownerEmails": [
            f"sa-dataproc-serverless@{project}.iam.gserviceaccount.com"
        ],
        "labels": {
            "env": conf["env"],
            "medallion_tier": "gold",
            "sla": "hourly",
        },
    }
    create_resp = client.post(url, payload, params={"dataProductId": product_id})
    if create_resp.status_code in (200, 201):
        logger.info("Successfully provisioned Dataplex Data Product: %s", product_id)
    else:
        logger.warning(
            "Data product check/creation returned %d: %s",
            create_resp.status_code, create_resp.text
        )


def ensure_aspect_type(client: GCPRestClient, conf: Dict[str, str]) -> str:
    """Ensure Aspect Type 'medallion-governance-template' is defined."""
    project = conf["project_id"]
    location = conf["location"]
    aspect_id = conf["aspect_id"]
    url = f"https://dataplex.googleapis.com/v1/projects/{project}/locations/{location}/aspectTypes"

    check_url = f"{url}/{aspect_id}"
    resp = client.get(check_url)
    if resp.status_code == 200:
        logger.info("AspectType '%s' exists.", aspect_id)
        return aspect_id

    payload = {
        "metadataTemplate": {
            "name": aspect_id,
            "type": "record",
            "recordFields": [
                {"name": "data_steward", "type": "string", "index": 1, "constraints": {"required": True}},
                {"name": "pii_classification", "type": "string", "index": 2, "constraints": {"required": True}},
                {"name": "medallion_tier", "type": "string", "index": 3, "constraints": {"required": True}},
                {"name": "sla_freshness_hours", "type": "int", "index": 4, "constraints": {"required": True}},
                {"name": "lifecycle_env", "type": "string", "index": 5, "constraints": {"required": True}},
                {"name": "ssn_masked", "type": "bool", "index": 6, "constraints": {"required": True}},
            ],
        },
        "displayName": "Medallion Governance Template",
        "description": "Medallion Governance Card for Data Mesh",
        "labels": {"env": conf["env"], "workload": "fraud_lakehouse"},
    }
    create_resp = client.post(url, payload, params={"aspectTypeId": aspect_id})
    if create_resp.status_code in (200, 201):
        logger.info("Successfully registered AspectType: %s", aspect_id)
    else:
        logger.info("AspectType check/creation returned status %d: %s", create_resp.status_code, create_resp.text)
    return aspect_id


def attach_aspect_to_entry(
    client: GCPRestClient,
    conf: Dict[str, str],
    project_number: str,
    dataset_id: str,
    table_id: str,
    medallion_tier: str,
    ssn_masked: bool,
) -> None:
    """Attach or update the medallion-governance-template aspect on a BigQuery table entry."""
    project = conf["project_id"]
    location = conf["location"]
    aspect_id = conf["aspect_id"]
    aspect_key = f"{project_number}.{location}.{aspect_id}"

    entry_name = f"projects/{project}/locations/{location}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{project}/datasets/{dataset_id}/tables/{table_id}"

    aspect_payload = {
        "aspects": {
            aspect_key: {
                "aspectType": f"projects/{project}/locations/{location}/aspectTypes/{aspect_id}",
                "data": {
                    "data_steward": "dpatel@acme.com",
                    "pii_classification": "restricted_confidential",
                    "medallion_tier": medallion_tier,
                    "sla_freshness_hours": 1,
                    "lifecycle_env": conf["env"].upper(),
                    "ssn_masked": ssn_masked,
                },
            }
        }
    }

    url = f"https://dataplex.googleapis.com/v1/{entry_name}"
    resp = client.patch(url, aspect_payload, params={"updateMask": "aspects", "aspectKeys": aspect_key})
    if resp.status_code == 200:
        logger.info(
            "Attached aspect to %s.%s [Tier: %s, SSN Masked: %s]",
            dataset_id, table_id, medallion_tier, ssn_masked
        )
    else:
        logger.warning(
            "Could not attach aspect to %s.%s (HTTP %d): %s",
            dataset_id, table_id, resp.status_code, resp.text
        )


def apply_policy_tag_and_masking(client: GCPRestClient, conf: Dict[str, str]) -> None:
    """Apply Policy Tag 'SSN_Cardholder' and Dynamic Data Masking to Bronze SSN columns."""
    project = conf["project_id"]
    location = conf["location"]
    lakehouse_ds = conf["lakehouse_dataset"]

    logger.info("Ensuring Data Catalog Taxonomy & Policy Tag SSN_Cardholder in %s...", location)
    tax_url = f"https://datacatalog.googleapis.com/v1/projects/{project}/locations/{location}/taxonomies"
    list_resp = client.get(tax_url)
    taxonomy_name = ""
    tag_name = ""

    if list_resp.status_code == 200:
        taxonomies = list_resp.json().get("taxonomies", [])
        for tax in taxonomies:
            if "pii_taxonomy" in tax.get("displayName", ""):
                taxonomy_name = tax.get("name", "")
                break

    if not taxonomy_name:
        tax_display_name = f"pii_taxonomy_{conf['env']}"
        create_tax_resp = client.post(tax_url, {
            "displayName": tax_display_name,
            "description": "Taxonomy for PII Access Control & Dynamic Data Masking",
            "activatedPolicyTypes": ["FINE_GRAINED_ACCESS_CONTROL"],
        })
        if create_tax_resp.status_code in (200, 201):
            taxonomy_name = create_tax_resp.json().get("name", "")
            logger.info("Created taxonomy: %s", taxonomy_name)
        else:
            logger.warning("Failed to create taxonomy: %s", create_tax_resp.text)

    if taxonomy_name:
        tag_url = f"https://datacatalog.googleapis.com/v1/{taxonomy_name}/policyTags"
        tag_resp = client.get(tag_url)
        if tag_resp.status_code == 200:
            for pt in tag_resp.json().get("policyTags", []):
                if pt.get("displayName") == "SSN_Cardholder":
                    tag_name = pt.get("name", "")
                    break

        if not tag_name:
            create_pt_resp = client.post(tag_url, {
                "displayName": "SSN_Cardholder",
                "description": "Direct cardholder Social Security Number requiring SHA256 dynamic masking",
            })
            if create_pt_resp.status_code in (200, 201):
                tag_name = create_pt_resp.json().get("name", "")
                logger.info("Created policy tag: %s", tag_name)

    if tag_name:
        logger.info("Policy Tag SSN_Cardholder is active: %s", tag_name)

        # Ensure BigQuery Dynamic Data Masking policy exists
        dp_url = f"https://bigquerydatapolicy.googleapis.com/v1/projects/{project}/locations/{location}/dataPolicies"
        dp_id = "ssn_cardholder_masking_policy"
        check_dp_resp = client.get(f"{dp_url}/{dp_id}")
        if check_dp_resp.status_code == 200:
            logger.info("BigQuery Data Policy '%s' already exists.", dp_id)
        else:
            dp_payload = {
                "dataPolicyType": "DATA_MASKING_POLICY",
                "dataPolicyId": dp_id,
                "policyTag": tag_name,
                "dataMaskingPolicy": {
                    "predefinedExpression": "SHA256"
                }
            }
            dp_resp = client.post(dp_url, dp_payload)
            if dp_resp.status_code in (200, 201):
                logger.info("Created BigQuery Dynamic Data Masking policy: %s", dp_id)
            else:
                logger.warning("Data policy check/creation returned %d: %s", dp_resp.status_code, dp_resp.text)

        # Apply policy tag to Bronze tables in BigQuery schema
        for target_table in ["customers_crm_bronze", "payment_transactions_bronze"]:
            tbl_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{project}/datasets/{lakehouse_ds}/tables/{target_table}"
            tbl_resp = client.get(tbl_url)
            if tbl_resp.status_code == 200:
                tbl_json = tbl_resp.json()
                fields = tbl_json.get("schema", {}).get("fields", [])
                updated = False
                for field in fields:
                    if field.get("name") == "ssn":
                        field["policyTags"] = {"names": [tag_name]}
                        updated = True
                if updated:
                    patch_resp = client.patch(tbl_url, {"schema": {"fields": fields}})
                    if patch_resp.status_code == 200:
                        logger.info("Successfully bound SSN_Cardholder policy tag to %s.ssn", target_table)
                    else:
                        logger.warning("Could not patch table %s: %s", target_table, patch_resp.text)


def run_governance_pipeline(conf: Dict[str, str]) -> None:
    """Execute full Data Mesh Pattern 2 governance setup."""
    client = GCPRestClient(conf["project_id"], conf["location"])
    project_number = client.get_project_number()
    logger.info("Resolved Project Number: %s", project_number)

    # 1. Provision Domain, Product, and AspectType
    ensure_dataplex_domain(client, conf)
    ensure_data_product(client, conf)
    ensure_aspect_type(client, conf)

    # 2. Attach Governance Aspect Card to All 11 BigQuery Entries
    # 5 Bronze Tables (ssn_masked=False)
    bronze_tables = [
        "customers_crm_bronze",
        "merchants_stores_bronze",
        "device_auth_logs_bronze",
        "payment_transactions_bronze",
        "chargeback_disputes_bronze",
    ]
    for tbl in bronze_tables:
        attach_aspect_to_entry(
            client, conf, project_number, conf["lakehouse_dataset"], tbl,
            medallion_tier="BRONZE", ssn_masked=False
        )

    # 5 Silver Tables (ssn_masked=True)
    silver_tables = [
        "customers_crm_silver",
        "merchants_stores_silver",
        "device_auth_logs_silver",
        "payment_transactions_silver",
        "chargeback_disputes_silver",
    ]
    for tbl in silver_tables:
        attach_aspect_to_entry(
            client, conf, project_number, conf["lakehouse_dataset"], tbl,
            medallion_tier="SILVER", ssn_masked=True
        )

    # 1 Gold Table (ssn_masked=True)
    attach_aspect_to_entry(
        client, conf, project_number, conf["gold_dataset"], "gold_fraud_features",
        medallion_tier="GOLD", ssn_masked=True
    )

    # 3. Apply Policy Tag & Dynamic Data Masking
    apply_policy_tag_and_masking(client, conf)

    logger.info("=== Data Mesh Governance & Privacy Policy Enforcement Complete ===")


def main() -> None:
    conf = load_config()
    run_governance_pipeline(conf)


if __name__ == "__main__":
    main()
