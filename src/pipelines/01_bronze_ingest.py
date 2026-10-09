#!/usr/bin/env python3
"""
ACME Global Payment Fraud Lakehouse - Bronze Ingestion Pipeline
Step 05 Production Script: 01_bronze_ingest.py

Business Objective:
Execute lossless 1:1 ingestion of all 5 raw feeds (15,506,500 records) from
Cloud Storage landing bucket into Apache Iceberg V2 tables within the BigLake
Bronze REST catalog (acme_bronze_dev.fraud_detection_db).
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Tuple
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, input_file_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("acme_bronze_ingest")


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
        "env": config.get("env", os.environ.get("ENV", "dev")),
        "region": config.get("primary-region", os.environ.get("REGION", "us-central1")),
        "raw_landing_bucket": config.get(
            "raw-landing-bucket",
            os.environ.get("RAW_LANDING_BUCKET", "acme-l400-part3-eri-01-raw-landing"),
        ),
        "lakehouse_warehouse_bucket": config.get(
            "lakehouse-warehouse-bucket",
            os.environ.get("LAKEHOUSE_WAREHOUSE_BUCKET", "acme-l400-part3-eri-01-lakehouse-warehouse"),
        ),
        "bronze_catalog": config.get(
            "biglake-bronze-catalog",
            os.environ.get("BIGLAKE_BRONZE_CATALOG", "acme_bronze_dev"),
        ),
        "lakehouse_dataset": config.get(
            "bigquery-lakehouse-dataset",
            os.environ.get("BIGQUERY_LAKEHOUSE_DATASET", "fraud_detection_db"),
        ),
    }


def init_spark_session(conf: Dict[str, str]) -> SparkSession:
    """Initialize SparkSession configured with BigLake Iceberg REST Catalog."""
    catalog = conf["bronze_catalog"]
    project_id = conf["project_id"]
    warehouse = f"bl://projects/{project_id}/catalogs/{catalog}"

    logger.info("Initializing SparkSession with Bronze Catalog: %s", catalog)
    builder = (
        SparkSession.builder
        .appName("ACME-Fraud-Lakehouse-01-Bronze-Ingest")
        .config("spark.dataproc.engine", "lightningEngine")
        .config("spark.dataproc.cohort", "fraud_benchmark")
        .config("spark.dataproc.lineage.enabled", "true")
        .config(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.type", "rest")
        .config(f"spark.sql.catalog.{catalog}.uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        .config(f"spark.sql.catalog.{catalog}.header.x-goog-user-project", project_id)
        .config(f"spark.sql.catalog.{catalog}.rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager")
        .config(f"spark.sql.catalog.{catalog}.io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO")
        .config(f"spark.sql.catalog.{catalog}.header.X-Iceberg-Access-Delegation", "vended-credentials")
        .config(f"spark.sql.catalog.{catalog}.vended-credentials-enabled", "true")
        .config("spark.sql.defaultCatalog", catalog)
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    )
    spark = builder.getOrCreate()
    try:
        spark.catalog.setCurrentCatalog(catalog)
    except Exception as e:
        logger.warning("Could not set current catalog: %s", e)
    return spark


def cast_all_columns_to_string(df: DataFrame) -> DataFrame:
    """Ensure all business columns are preserved as StringType for lossless ingestion."""
    select_exprs = [col(c).cast("string").alias(c) for c in df.columns]
    return df.select(*select_exprs)


def ingest_feed(
    spark: SparkSession,
    feed_name: str,
    raw_path: str,
    file_format: str,
    target_table_name: str,
    catalog: str,
    dataset: str,
) -> int:
    """Read a raw feed permissively and write lossless mirror to Iceberg V2."""
    logger.info("Processing feed [%s] from %s (format: %s)", feed_name, raw_path, file_format)

    if file_format == "csv":
        # Required settings for CRLF preservation in merchants_stores
        raw_df = (
            spark.read
            .option("header", "true")
            .option("multiLine", "true")
            .option("escape", "\"")
            .option("mode", "PERMISSIVE")
            .csv(raw_path)
        )
    elif file_format == "json":
        raw_df = (
            spark.read
            .option("mode", "PERMISSIVE")
            .json(raw_path)
        )
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

    # Enforce permissive all-string types and append mandatory audit metadata
    string_df = cast_all_columns_to_string(raw_df)
    bronze_df = (
        string_df
        .withColumn("_ingestion_timestamp", current_timestamp())
        .withColumn("_source_file", input_file_name())
    )

    full_target_table = f"{catalog}.{dataset}.{target_table_name}"
    logger.info("Writing to Iceberg V2 table: %s", full_target_table)

    # Ensure database/namespace exists in Iceberg catalog
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS `{catalog}`.{dataset}")

    # Write using Iceberg createOrReplace with format-version=2
    (
        bronze_df.writeTo(f"`{catalog}`.{dataset}.{target_table_name}")
        .using("iceberg")
        .tableProperty("format-version", "2")
        .createOrReplace()
    )

    row_count = spark.table(f"`{catalog}`.{dataset}.{target_table_name}").count()
    logger.info("Successfully ingested [%s] -> %s: %d rows", feed_name, full_target_table, row_count)
    return row_count


def run_bronze_ingestion(config: Dict[str, str]) -> Dict[str, int]:
    """Execute Bronze ingestion across all 5 raw feeds."""
    spark = init_spark_session(config)

    raw_base = f"gs://{config['raw_landing_bucket']}/v0.01"
    catalog = config["bronze_catalog"]
    dataset = config["lakehouse_dataset"]

    # 5 Source Feeds Contract
    feeds: List[Tuple[str, str, str, str, int]] = [
        ("customers_crm", f"{raw_base}/customers_crm", "json", "customers_crm_bronze", 510000),
        ("merchants_stores", f"{raw_base}/merchants_stores", "csv", "merchants_stores_bronze", 26000),
        ("device_auth_logs", f"{raw_base}/device_auth_logs", "json", "device_auth_logs_bronze", 4120000),
        ("payment_transactions", f"{raw_base}/payment_transactions", "json", "payment_transactions_bronze", 10490000),
        ("chargeback_disputes", f"{raw_base}/chargeback_disputes", "json", "chargeback_disputes_bronze", 360500),
    ]

    results: Dict[str, int] = {}
    total_ingested = 0

    for feed_name, path, fmt, target_table, expected_count in feeds:
        count = ingest_feed(spark, feed_name, path, fmt, target_table, catalog, dataset)
        results[target_table] = count
        total_ingested += count
        if count != expected_count:
            logger.warning(
                "Count mismatch for %s: got %d, expected %d",
                target_table, count, expected_count
            )

    logger.info("=== Bronze Ingestion Complete ===")
    logger.info("Total rows ingested across 5 tables: %d (Expected: 15,506,500)", total_ingested)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="ACME Fraud Lakehouse - Bronze Ingestion")
    parser.add_argument("--project-id", type=str, help="GCP Project ID")
    parser.add_argument("--env", type=str, default="dev", help="Deployment environment (dev, qa, prod)")
    parser.add_argument("--raw-bucket", type=str, help="Raw Landing GCS Bucket")
    parser.add_argument("--warehouse-bucket", type=str, help="Lakehouse Warehouse GCS Bucket")
    parser.add_argument("--catalog", type=str, help="BigLake Bronze Catalog Name")
    parser.add_argument("--dataset", type=str, help="Lakehouse BigQuery Dataset Name")
    args = parser.parse_args()

    conf = load_config()
    if args.project_id:
        conf["project_id"] = args.project_id
    if args.env:
        conf["env"] = args.env
    if args.raw_bucket:
        conf["raw_landing_bucket"] = args.raw_bucket
    if args.warehouse_bucket:
        conf["lakehouse_warehouse_bucket"] = args.warehouse_bucket
    if args.catalog:
        conf["bronze_catalog"] = args.catalog
    if args.dataset:
        conf["lakehouse_dataset"] = args.dataset

    run_bronze_ingestion(conf)


if __name__ == "__main__":
    main()
