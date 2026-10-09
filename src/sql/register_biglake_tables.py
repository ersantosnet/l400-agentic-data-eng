#!/usr/bin/env python3
"""
ACME Global Payment Fraud Lakehouse - BigLake Table Registration
Registers Apache Iceberg V2 Bronze and Silver tables in BigQuery dataset fraud_detection_db.
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("register_biglake_tables")

PROJECT_ID = "acme-l400-part3-eri-01"
CONNECTION_ID = f"{PROJECT_ID}.us-central1.lakehouse-vending-conn"
DATASET = "fraud_detection_db"

def get_metadata_location(catalog: str, table: str) -> str:
    cmd = [
        "gcloud", "biglake", "iceberg", "tables", "describe", table,
        f"--namespace={DATASET}",
        f"--catalog={catalog}",
        f"--project={PROJECT_ID}",
        "--format=value(metadata-location)"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()

def create_external_table(table_name: str, metadata_uri: str) -> None:
    ddl = f"""
    CREATE OR REPLACE EXTERNAL TABLE `{PROJECT_ID}.{DATASET}.{table_name}`
    WITH CONNECTION `{CONNECTION_ID}`
    OPTIONS (
      format = 'ICEBERG',
      uris = ['{metadata_uri}']
    );
    """
    logger.info("Registering %s in BigQuery...", table_name)
    cmd = ["bq", "query", "--use_legacy_sql=false", ddl]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    logger.info("Successfully registered %s: %s", table_name, res.stdout.strip())

def main() -> None:
    bronze_tables = [
        "customers_crm_bronze",
        "merchants_stores_bronze",
        "device_auth_logs_bronze",
        "payment_transactions_bronze",
        "chargeback_disputes_bronze"
    ]
    silver_tables = [
        "customers_crm_silver",
        "merchants_stores_silver",
        "device_auth_logs_silver",
        "payment_transactions_silver",
        "chargeback_disputes_silver"
    ]

    for tbl in bronze_tables:
        uri = get_metadata_location("acme_bronze_dev", tbl)
        create_external_table(tbl, uri)

    for tbl in silver_tables:
        uri = get_metadata_location("acme_silver_dev", tbl)
        create_external_table(tbl, uri)

    logger.info("All 10 Bronze and Silver BigLake Iceberg tables registered in BigQuery!")

if __name__ == "__main__":
    main()
