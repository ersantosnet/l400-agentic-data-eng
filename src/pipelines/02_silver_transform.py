#!/usr/bin/env python3
"""
ACME Global Payment Fraud Lakehouse - Silver Cleansing & Transformation Pipeline
Step 05 Production Script: 02_silver_transform.py

Business Objective:
Execute SIMD-accelerated, high-precision Silver cleansing and deduplication on
Dataproc Serverless Spark 2.3 with Lightning Engine (spark.dataproc.engine=lightningEngine).
Transforms 15,506,500 Bronze rows into exactly 14,875,000 clean unique records across
5 Apache Iceberg V2 Merge-on-Read (MoR) tables in acme_silver_dev.fraud_detection_db.
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql.functions import (
    broadcast,
    col,
    current_timestamp,
    expr,
    lit,
    lower,
    radians,
    regexp_replace,
    row_number,
    sha2,
    trim,
    upper,
    when,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("acme_silver_transform")


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
        "lakehouse_warehouse_bucket": config.get(
            "lakehouse-warehouse-bucket",
            os.environ.get("LAKEHOUSE_WAREHOUSE_BUCKET", "acme-l400-part3-eri-01-lakehouse-warehouse"),
        ),
        "bronze_catalog": config.get(
            "biglake-bronze-catalog",
            os.environ.get("BIGLAKE_BRONZE_CATALOG", "acme_bronze_dev"),
        ),
        "silver_catalog": config.get(
            "biglake-silver-catalog",
            os.environ.get("BIGLAKE_SILVER_CATALOG", "acme_silver_dev"),
        ),
        "lakehouse_dataset": config.get(
            "bigquery-lakehouse-dataset",
            os.environ.get("BIGQUERY_LAKEHOUSE_DATASET", "fraud_detection_db"),
        ),
    }


def init_spark_session(conf: Dict[str, str]) -> SparkSession:
    """Initialize SparkSession configured with dual BigLake Iceberg REST Catalogs."""
    bronze_cat = conf["bronze_catalog"]
    silver_cat = conf["silver_catalog"]
    project_id = conf["project_id"]

    logger.info("Initializing SparkSession with Bronze (%s) and Silver (%s) Catalogs", bronze_cat, silver_cat)
    builder = (
        SparkSession.builder
        .appName("ACME-Fraud-Lakehouse-02-Silver-Transform")
        .config("spark.dataproc.engine", "lightningEngine")
        .config("spark.dataproc.cohort", "fraud_benchmark")
        .config("spark.dataproc.lineage.enabled", "true")
        # Bronze Catalog
        .config(f"spark.sql.catalog.{bronze_cat}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{bronze_cat}.type", "rest")
        .config(f"spark.sql.catalog.{bronze_cat}.uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog")
        .config(f"spark.sql.catalog.{bronze_cat}.warehouse", f"bl://projects/{project_id}/catalogs/{bronze_cat}")
        .config(f"spark.sql.catalog.{bronze_cat}.header.x-goog-user-project", project_id)
        .config(f"spark.sql.catalog.{bronze_cat}.rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager")
        .config(f"spark.sql.catalog.{bronze_cat}.io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO")
        .config(f"spark.sql.catalog.{bronze_cat}.header.X-Iceberg-Access-Delegation", "vended-credentials")
        .config(f"spark.sql.catalog.{bronze_cat}.vended-credentials-enabled", "true")
        # Silver Catalog
        .config(f"spark.sql.catalog.{silver_cat}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{silver_cat}.type", "rest")
        .config(f"spark.sql.catalog.{silver_cat}.uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog")
        .config(f"spark.sql.catalog.{silver_cat}.warehouse", f"bl://projects/{project_id}/catalogs/{silver_cat}")
        .config(f"spark.sql.catalog.{silver_cat}.header.x-goog-user-project", project_id)
        .config(f"spark.sql.catalog.{silver_cat}.rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager")
        .config(f"spark.sql.catalog.{silver_cat}.io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO")
        .config(f"spark.sql.catalog.{silver_cat}.header.X-Iceberg-Access-Delegation", "vended-credentials")
        .config(f"spark.sql.catalog.{silver_cat}.vended-credentials-enabled", "true")
        .config("spark.sql.defaultCatalog", silver_cat)
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    )
    spark = builder.getOrCreate()
    try:
        spark.catalog.setCurrentCatalog(silver_cat)
    except Exception as e:
        logger.warning("Could not set current catalog: %s", e)
    return spark


def clean_numeric_sql(c: str, target_type: str = "decimal(18,2)") -> str:
    """Generate ANSI-safe Velox SIMD SQL expression to sanitize currency, noise, and acct parentheses."""
    return f"""
    case 
      when `{c}` is null then null
      when rlike(cast(`{c}` as string), '^\\\\s*\\\\(\\\\s*\\\\$?\\\\s*[0-9]') then
        -try_cast(regexp_extract(regexp_replace(cast(`{c}` as string), '[,\\\\$*#!~\\\\u00a0\\\\u200b\\\\t]|USD|pts|%|ms|deg\\\\s+[NSEW]|\\\\(high\\\\)', ''), '([0-9]+(?:\\\\.[0-9]+)?)', 1) as {target_type})
      else
        try_cast(regexp_extract(regexp_replace(cast(`{c}` as string), '[,\\\\$*#!~\\\\u00a0\\\\u200b\\\\t]|USD|pts|%|ms|deg\\\\s+[NSEW]|\\\\(high\\\\)', ''), '(-?[0-9]+(?:\\\\.[0-9]+)?)', 1) as {target_type})
    end
    """


def parse_timestamp_sql(c: str) -> str:
    """Generate ANSI-safe multi-format timestamp parser expression."""
    clean_ts = f"trim(regexp_replace(cast(`{c}` as string), '\\\\s*UTC$', ''))"
    return f"""
    coalesce(
      try_to_timestamp({clean_ts}),
      try_to_timestamp({clean_ts}, 'yyyy/MM/dd HH:mm:ss'),
      try_to_timestamp({clean_ts}, 'yyyy-MM-dd HH:mm:ss'),
      try_to_timestamp({clean_ts}, 'MM/dd/yyyy HH:mm:ss'),
      try_to_timestamp({clean_ts}, 'dd-MM-yyyy HH:mm:ss')
    )
    """


def clean_key_sql(c: str) -> str:
    """Generate ANSI-safe key normalizer: upper, trim, strip noise."""
    return f"upper(trim(regexp_replace(cast(`{c}` as string), '[*#!~\\\\u00a0\\\\u200b\\\\t\\\\s]+', '')))"


def write_silver_iceberg_table(
    spark: SparkSession,
    df: DataFrame,
    catalog: str,
    dataset: str,
    table_name: str,
) -> int:
    """Write DataFrame as Iceberg V2 MoR table and return row count."""
    target_table = f"`{catalog}`.{dataset}.{table_name}"
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS `{catalog}`.{dataset}")

    logger.info("Writing clean records to Iceberg V2 MoR table: %s", target_table)
    (
        df.writeTo(target_table)
        .using("iceberg")
        .tableProperty("format-version", "2")
        .tableProperty("write.delete.mode", "merge-on-read")
        .tableProperty("write.update.mode", "merge-on-read")
        .tableProperty("write.merge.mode", "merge-on-read")
        .createOrReplace()
    )
    row_count = spark.table(target_table).count()
    logger.info("Table %s materialized successfully with %d rows", target_table, row_count)
    return row_count


def transform_customers(spark: SparkSession, bronze_cat: str, dataset: str) -> DataFrame:
    """Transform and deduplicate customers_crm_bronze -> customers_crm_silver (500,000 clean rows)."""
    logger.info("Cleansing customers_crm_bronze...")
    source_df = spark.table(f"`{bronze_cat}`.{dataset}.customers_crm_bronze")

    # 1. Cleanse keys, timestamps, numerics, and PII
    cleaned = (
        source_df
        .withColumn("clean_pk", expr(clean_key_sql("customer_id")))
        .withColumn("clean_signup_ts", expr(parse_timestamp_sql("signup_timestamp")))
        .withColumn("clean_credit_limit", expr(clean_numeric_sql("credit_limit_usd", "decimal(18,2)")))
        .withColumn("clean_reward_points", expr(f"coalesce({clean_numeric_sql('reward_points', 'bigint')}, 0L)"))
        .withColumn("clean_home_lat", expr(clean_numeric_sql("home_lat", "double")))
        .withColumn("clean_home_lon", expr(clean_numeric_sql("home_lon", "double")))
        .withColumn(
            "clean_loyalty_tier",
            when(
                col("loyalty_tier").isNotNull() & (trim(col("loyalty_tier")) != ""),
                upper(trim(regexp_replace(col("loyalty_tier"), r"[\*#!\u00a0\u200b\t ]", "")))
            ).otherwise(lit(None))
        )
        # Cryptographic PII Pseudonymization
        .withColumn("masked_ssn", sha2(lower(trim(col("ssn"))), 256))
        .withColumn("masked_email", sha2(lower(trim(col("email"))), 256))
        .withColumn(
            "masked_phone",
            when(col("phone").isNotNull() & (trim(col("phone")) != ""),
                 sha2(regexp_replace(trim(col("phone")), r"[^0-9+]", ""), 256))
            .otherwise(lit(None))
        )
        .withColumn(
            "masked_billing_address",
            when(col("billing_address").isNotNull() & (trim(col("billing_address")) != ""),
                 sha2(lower(trim(regexp_replace(col("billing_address"), r"[\t\u00a0\u200b]+", " "))), 256))
            .otherwise(lit(None))
        )
    )

    # 2. Enforce 4-Class Null Contract:
    # Filter Class N1/N2/N3a (valid PK, non-null signup timestamp), Class N3b (credit_limit > 0)
    valid_rows = cleaned.filter(
        (col("clean_pk").isNotNull()) & (col("clean_pk") != "") &
        (col("clean_signup_ts").isNotNull()) &
        (col("clean_credit_limit").isNotNull()) & (col("clean_credit_limit") > 0)
    )

    # 3. Window Deduplication: Keep latest record per customer_id
    window_spec = Window.partitionBy("clean_pk").orderBy(col("clean_signup_ts").desc(), col("_ingestion_timestamp").desc())
    deduped = (
        valid_rows
        .withColumn("rn", row_number().over(window_spec))
        .filter(col("rn") == 1)
        .drop("rn")
    )

    # 4. Final Projection: Drop cleartext SSN and email
    final_df = deduped.select(
        col("clean_pk").alias("customer_id"),
        col("clean_signup_ts").alias("signup_timestamp"),
        trim(col("full_name")).alias("full_name"),
        col("masked_ssn"),
        col("masked_email"),
        trim(col("phone")).alias("phone"),
        col("masked_phone"),
        col("clean_loyalty_tier").alias("loyalty_tier"),
        col("clean_credit_limit").alias("credit_limit_usd"),
        col("clean_reward_points").alias("reward_points"),
        col("clean_home_lat").alias("home_lat"),
        col("clean_home_lon").alias("home_lon"),
        trim(col("billing_address")).alias("billing_address"),
        col("masked_billing_address"),
        col("snapshot_date"),
        current_timestamp().alias("_silver_cleansed_at"),
    )
    return final_df


def transform_merchants(spark: SparkSession, bronze_cat: str, dataset: str) -> DataFrame:
    """Transform and deduplicate merchants_stores_bronze -> merchants_stores_silver (25,000 clean rows)."""
    logger.info("Cleansing merchants_stores_bronze...")
    source_df = spark.table(f"`{bronze_cat}`.{dataset}.merchants_stores_bronze")

    cleaned = (
        source_df
        .withColumn("clean_pk", expr(clean_key_sql("merchant_id")))
        .withColumn("clean_monthly_fee", expr(clean_numeric_sql("terminal_monthly_fee_usd", "decimal(18,2)")))
        .withColumn("clean_comm_rate", expr(f"coalesce({clean_numeric_sql('commission_rate_pct', 'double')}, 0.0)"))
        .withColumn("clean_lat", expr(clean_numeric_sql("store_lat", "double")))
        .withColumn("clean_lon", expr(clean_numeric_sql("store_lon", "double")))
    )

    # Enforce 4-Class Null Contract: valid merchant_id and monthly fee > 0
    valid_rows = cleaned.filter(
        (col("clean_pk").isNotNull()) & (col("clean_pk") != "") &
        (col("clean_monthly_fee").isNotNull()) & (col("clean_monthly_fee") > 0)
    )

    window_spec = Window.partitionBy("clean_pk").orderBy(col("snapshot_date").desc(), col("_ingestion_timestamp").desc())
    deduped = (
        valid_rows
        .withColumn("rn", row_number().over(window_spec))
        .filter(col("rn") == 1)
        .drop("rn")
    )

    final_df = deduped.select(
        col("clean_pk").alias("merchant_id"),
        trim(col("store_name")).alias("store_name"),
        upper(trim(regexp_replace(col("merchant_category"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("merchant_category"),
        upper(trim(col("channel_type"))).alias("channel_type"),
        col("clean_monthly_fee").alias("terminal_monthly_fee_usd"),
        col("clean_comm_rate").alias("commission_rate_pct"),
        col("clean_lat").alias("store_lat"),
        col("clean_lon").alias("store_lon"),
        upper(trim(regexp_replace(col("risk_tier"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("risk_tier"),
        trim(col("store_manager_code")).alias("store_manager_code"),
        trim(col("region_notes")).alias("region_notes"),
        col("snapshot_date"),
        current_timestamp().alias("_silver_cleansed_at"),
    )
    return final_df


def transform_device_auth(spark: SparkSession, bronze_cat: str, dataset: str) -> DataFrame:
    """Transform and deduplicate device_auth_logs_bronze -> device_auth_logs_silver (4,000,000 clean rows)."""
    logger.info("Cleansing device_auth_logs_bronze...")
    source_df = spark.table(f"`{bronze_cat}`.{dataset}.device_auth_logs_bronze")

    cleaned = (
        source_df
        .withColumn("clean_pk", expr(clean_key_sql("session_id")))
        .withColumn("clean_customer_id", expr(clean_key_sql("customer_id")))
        .withColumn("clean_device_id", expr(clean_key_sql("device_id")))
        .withColumn("clean_login_ts", expr(parse_timestamp_sql("login_timestamp")))
        .withColumn("clean_latency", expr(clean_numeric_sql("auth_latency_ms", "double")))
        .withColumn("clean_risk_score", expr(f"coalesce({clean_numeric_sql('risk_score_raw', 'double')}, 0.0)"))
        .withColumn("clean_lat", expr(clean_numeric_sql("login_lat", "double")))
        .withColumn("clean_lon", expr(clean_numeric_sql("login_lon", "double")))
        .withColumn(
            "masked_device_ip",
            when(col("device_ip").isNotNull() & (trim(col("device_ip")) != ""),
                 sha2(trim(col("device_ip")), 256))
            .otherwise(lit(None))
        )
    )

    # 4-Class Null Contract: valid session_id, customer_id, device_id, non-null timestamp, latency > 0
    valid_rows = cleaned.filter(
        (col("clean_pk").isNotNull()) & (col("clean_pk") != "") &
        (col("clean_customer_id").isNotNull()) & (col("clean_customer_id") != "") &
        (col("clean_device_id").isNotNull()) & (col("clean_device_id") != "") &
        (col("clean_login_ts").isNotNull()) &
        (col("clean_latency").isNotNull()) & (col("clean_latency") > 0)
    )

    window_spec = Window.partitionBy("clean_pk").orderBy(col("clean_login_ts").desc(), col("_ingestion_timestamp").desc())
    deduped = (
        valid_rows
        .withColumn("rn", row_number().over(window_spec))
        .filter(col("rn") == 1)
        .drop("rn")
    )

    final_df = deduped.select(
        col("clean_pk").alias("session_id"),
        col("clean_customer_id").alias("customer_id"),
        col("clean_device_id").alias("device_id"),
        col("clean_login_ts").alias("login_timestamp"),
        upper(trim(regexp_replace(col("auth_event"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("auth_event"),
        col("clean_latency").alias("auth_latency_ms"),
        col("clean_risk_score").alias("risk_score_raw"),
        col("clean_lat").alias("login_lat"),
        col("clean_lon").alias("login_lon"),
        col("masked_device_ip"),
        trim(col("user_agent")).alias("user_agent"),
        upper(trim(col("mfa_method"))).alias("mfa_method"),
        col("year"),
        col("month"),
        col("day"),
        current_timestamp().alias("_silver_cleansed_at"),
    )
    return final_df


def transform_payment_transactions(
    spark: SparkSession,
    bronze_cat: str,
    dataset: str,
    df_customers_silver: DataFrame,
) -> DataFrame:
    """Transform, deduplicate, and enrich payment_transactions (10,000,000 clean rows)."""
    logger.info("Cleansing payment_transactions_bronze...")
    source_df = spark.table(f"`{bronze_cat}`.{dataset}.payment_transactions_bronze")

    cleaned = (
        source_df
        .withColumn("clean_pk", expr(clean_key_sql("transaction_id")))
        .withColumn("clean_customer_id", expr(clean_key_sql("customer_id")))
        .withColumn("clean_merchant_id", expr(clean_key_sql("merchant_id")))
        .withColumn("clean_session_id", expr(clean_key_sql("session_id")))
        .withColumn("clean_device_id", expr(clean_key_sql("device_id")))
        .withColumn("clean_tx_ts", expr(parse_timestamp_sql("tx_timestamp")))
        .withColumn("clean_tx_amount", expr(clean_numeric_sql("tx_amount", "decimal(18,2)")))
        .withColumn("clean_discount_amount", expr(f"coalesce({clean_numeric_sql('discount_amount', 'decimal(18,2)')}, cast(0.00 as decimal(18,2)))"))
        .withColumn("clean_lat", expr(clean_numeric_sql("lat", "double")))
        .withColumn("clean_lon", expr(clean_numeric_sql("lon", "double")))
        .withColumn("clean_payment_method", expr("try_cast(regexp_replace(trim(payment_method), '[^0-9]', '') as int)"))
        .withColumn("clean_status", upper(trim(regexp_replace(col("gateway_status"), r"[\*#!\u00a0\u200b\t]", ""))))
        # Cryptographic PII Pseudonymization (Leaked SSN and IP)
        .withColumn("masked_ssn", sha2(lower(trim(col("ssn"))), 256))
        .withColumn(
            "masked_device_ip",
            when(col("device_ip").isNotNull() & (trim(col("device_ip")) != ""),
                 sha2(trim(col("device_ip")), 256))
            .otherwise(lit(None))
        )
    )

    # 4-Class Null Contract: valid transaction_id, customer_id, merchant_id, session_id, timestamp, tx_amount > 0
    valid_rows = cleaned.filter(
        (col("clean_pk").isNotNull()) & (col("clean_pk") != "") &
        (col("clean_customer_id").isNotNull()) & (col("clean_customer_id") != "") &
        (col("clean_merchant_id").isNotNull()) & (col("clean_merchant_id") != "") &
        (col("clean_session_id").isNotNull()) & (col("clean_session_id") != "") &
        (col("clean_tx_ts").isNotNull()) &
        (col("clean_tx_amount").isNotNull()) & (col("clean_tx_amount") > 0)
    )

    # Window Deduplication: Prioritize 'SETTLED' status and latest event timestamp to eliminate TIMEOUT_RETRY
    status_priority = when(col("clean_status") == "SETTLED", 2).otherwise(1)
    window_dedup = Window.partitionBy("clean_pk").orderBy(status_priority.desc(), col("clean_tx_ts").desc(), col("_ingestion_timestamp").desc())
    deduped = (
        valid_rows
        .withColumn("rn", row_number().over(window_dedup))
        .filter(col("rn") == 1)
        .drop("rn")
    )

    # Behavioral Enrichment 1: 1-hour transaction velocity per customer
    window_vel = (
        Window.partitionBy("clean_customer_id")
        .orderBy(col("clean_tx_ts").cast("long"))
        .rangeBetween(-3600, 0)
    )
    with_velocity = deduped.withColumn("velocity_1h", expr("count(clean_pk)").over(window_vel))

    # Behavioral Enrichment 2: Spherical Haversine distance from customer registered residence
    cust_coords = df_customers_silver.select(
        col("customer_id").alias("_cust_id"),
        col("home_lat").alias("_home_lat"),
        col("home_lon").alias("_home_lon"),
    )

    joined_with_cust = with_velocity.join(
        broadcast(cust_coords),
        with_velocity["clean_customer_id"] == cust_coords["_cust_id"],
        how="left",
    )

    # Spherical Haversine Distance (in kilometers, radius 6371.0 km)
    # distance = 6371.0 * 2 * asin(sqrt(sin^2(dlat/2) + cos(lat1)*cos(lat2)*sin^2(dlon/2)))
    dlat = radians(col("clean_lat")) - radians(col("_home_lat"))
    dlon = radians(col("clean_lon")) - radians(col("_home_lon"))
    haversine_expr = (
        lit(6371.0) * lit(2.0) * expr(
            "asin(sqrt(least(greatest(power(sin(dlat / 2), 2) + cos(radians(_home_lat)) * cos(radians(clean_lat)) * power(sin(dlon / 2), 2), 0.0), 1.0)))"
        )
    )

    enriched = (
        joined_with_cust
        .withColumn("dlat", dlat)
        .withColumn("dlon", dlon)
        .withColumn("geo_distance_km", when(col("_home_lat").isNotNull(), haversine_expr).otherwise(lit(0.0)))
        .drop("_cust_id", "_home_lat", "_home_lon", "dlat", "dlon")
    )

    # Final Projection: Strictly DROP raw SSN and email
    final_df = enriched.select(
        col("clean_pk").alias("transaction_id"),
        col("clean_customer_id").alias("customer_id"),
        col("clean_merchant_id").alias("merchant_id"),
        col("clean_session_id").alias("session_id"),
        col("clean_device_id").alias("device_id"),
        col("masked_ssn"),
        col("clean_tx_ts").alias("tx_timestamp"),
        col("clean_tx_amount").alias("tx_amount"),
        col("clean_discount_amount").alias("discount_amount"),
        (col("clean_tx_amount") - col("clean_discount_amount")).cast("decimal(18,2)").alias("net_amount_after_discount"),
        col("clean_payment_method").alias("payment_method"),
        col("clean_status").alias("gateway_status"),
        col("card_hash"),
        col("clean_lat").alias("lat"),
        col("clean_lon").alias("lon"),
        col("geo_distance_km"),
        col("velocity_1h"),
        trim(col("device_ip")).alias("device_ip"),
        col("masked_device_ip"),
        trim(col("promo_code")).alias("promo_code"),
        col("year"),
        col("month"),
        col("day"),
        current_timestamp().alias("_silver_cleansed_at"),
    )
    return final_df


def transform_chargeback_disputes(spark: SparkSession, bronze_cat: str, dataset: str) -> DataFrame:
    """Transform and deduplicate chargeback_disputes (350,000 clean rows)."""
    logger.info("Cleansing chargeback_disputes_bronze...")
    source_df = spark.table(f"`{bronze_cat}`.{dataset}.chargeback_disputes_bronze")

    cleaned = (
        source_df
        .withColumn("clean_pk", expr(clean_key_sql("dispute_id")))
        .withColumn("clean_tx_id", expr(clean_key_sql("transaction_id")))
        .withColumn("clean_customer_id", expr(clean_key_sql("customer_id")))
        .withColumn("clean_merchant_id", expr(clean_key_sql("merchant_id")))
        .withColumn("clean_dispute_ts", expr(parse_timestamp_sql("dispute_timestamp")))
        .withColumn("clean_dispute_amount", expr(clean_numeric_sql("dispute_amount", "decimal(18,2)")))
        .withColumn("clean_penalty_fee", expr(f"coalesce({clean_numeric_sql('penalty_fee_usd', 'decimal(18,2)')}, cast(0.00 as decimal(18,2)))"))
    )

    # 4-Class Null Contract: valid dispute_id, transaction_id, customer_id, merchant_id, timestamp, dispute_amount > 0
    valid_rows = cleaned.filter(
        (col("clean_pk").isNotNull()) & (col("clean_pk") != "") &
        (col("clean_tx_id").isNotNull()) & (col("clean_tx_id") != "") &
        (col("clean_customer_id").isNotNull()) & (col("clean_customer_id") != "") &
        (col("clean_merchant_id").isNotNull()) & (col("clean_merchant_id") != "") &
        (col("clean_dispute_ts").isNotNull()) &
        (col("clean_dispute_amount").isNotNull()) & (col("clean_dispute_amount") > 0)
    )

    window_spec = Window.partitionBy("clean_pk").orderBy(col("clean_dispute_ts").desc(), col("_ingestion_timestamp").desc())
    deduped = (
        valid_rows
        .withColumn("rn", row_number().over(window_spec))
        .filter(col("rn") == 1)
        .drop("rn")
    )

    # Check reason code vs dispute reason
    reason_expr = (
        upper(trim(regexp_replace(col("reason_code"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("reason_code")
        if "reason_code" in source_df.columns
        else upper(trim(regexp_replace(col("dispute_reason"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("reason_code")
    )
    res_status_expr = (
        upper(trim(regexp_replace(col("resolution_status"), r"[\*#!\u00a0\u200b\t ]", ""))).alias("resolution_status")
        if "resolution_status" in source_df.columns
        else lit(None).alias("resolution_status")
    )

    final_df = deduped.select(
        col("clean_pk").alias("dispute_id"),
        col("clean_tx_id").alias("transaction_id"),
        col("clean_customer_id").alias("customer_id"),
        col("clean_merchant_id").alias("merchant_id"),
        col("clean_dispute_ts").alias("dispute_timestamp"),
        col("clean_dispute_amount").alias("dispute_amount"),
        col("clean_penalty_fee").alias("penalty_fee_usd"),
        reason_expr,
        res_status_expr,
        trim(col("customer_statement")).alias("customer_statement"),
        trim(col("agent_notes")).alias("agent_notes"),
        col("year"),
        col("month"),
        col("day"),
        current_timestamp().alias("_silver_cleansed_at"),
    )
    return final_df


def run_silver_transform(config: Dict[str, str]) -> Dict[str, int]:
    """Execute Silver cleansing across all 5 tables."""
    spark = init_spark_session(config)

    bronze_cat = config["bronze_catalog"]
    silver_cat = config["silver_catalog"]
    dataset = config["lakehouse_dataset"]

    results: Dict[str, int] = {}

    # 1. Transform customers_crm_silver
    df_customers_silver = transform_customers(spark, bronze_cat, dataset)
    results["customers_crm_silver"] = write_silver_iceberg_table(
        spark, df_customers_silver, silver_cat, dataset, "customers_crm_silver"
    )

    # 2. Transform merchants_stores_silver
    df_merchants_silver = transform_merchants(spark, bronze_cat, dataset)
    results["merchants_stores_silver"] = write_silver_iceberg_table(
        spark, df_merchants_silver, silver_cat, dataset, "merchants_stores_silver"
    )

    # 3. Transform device_auth_logs_silver
    df_auth_silver = transform_device_auth(spark, bronze_cat, dataset)
    results["device_auth_logs_silver"] = write_silver_iceberg_table(
        spark, df_auth_silver, silver_cat, dataset, "device_auth_logs_silver"
    )

    # 4. Transform payment_transactions_silver (enriched with customer coordinates)
    df_tx_silver = transform_payment_transactions(spark, bronze_cat, dataset, df_customers_silver)
    results["payment_transactions_silver"] = write_silver_iceberg_table(
        spark, df_tx_silver, silver_cat, dataset, "payment_transactions_silver"
    )

    # 5. Transform chargeback_disputes_silver
    df_disputes_silver = transform_chargeback_disputes(spark, bronze_cat, dataset)
    results["chargeback_disputes_silver"] = write_silver_iceberg_table(
        spark, df_disputes_silver, silver_cat, dataset, "chargeback_disputes_silver"
    )

    total_silver = sum(results.values())
    logger.info("=== Silver Transformation Complete ===")
    logger.info("Total clean unique rows: %d (Target: exactly 14,875,000)", total_silver)
    for tbl, count in results.items():
        logger.info("  %s: %d rows", tbl, count)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="ACME Fraud Lakehouse - Silver Transformation")
    parser.add_argument("--project-id", type=str, help="GCP Project ID")
    parser.add_argument("--env", type=str, default="dev", help="Deployment environment (dev, qa, prod)")
    parser.add_argument("--warehouse-bucket", type=str, help="Lakehouse Warehouse GCS Bucket")
    parser.add_argument("--bronze-catalog", type=str, help="Bronze BigLake REST Catalog Name")
    parser.add_argument("--silver-catalog", type=str, help="Silver BigLake REST Catalog Name")
    parser.add_argument("--dataset", type=str, help="BigQuery Lakehouse Dataset Name")
    args = parser.parse_args()

    conf = load_config()
    if args.project_id:
        conf["project_id"] = args.project_id
    if args.env:
        conf["env"] = args.env
    if args.warehouse_bucket:
        conf["lakehouse_warehouse_bucket"] = args.warehouse_bucket
    if args.bronze_catalog:
        conf["bronze_catalog"] = args.bronze_catalog
    if args.silver_catalog:
        conf["silver_catalog"] = args.silver_catalog
    if args.dataset:
        conf["lakehouse_dataset"] = args.dataset

    run_silver_transform(conf)


if __name__ == "__main__":
    main()
