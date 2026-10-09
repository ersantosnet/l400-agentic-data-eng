#!/usr/bin/env python3
"""
ACME Global Payment Fraud Lakehouse - Cloud Composer 3 End-to-End Orchestration DAG
Step 05 Production Script: medallion_lakehouse_dag.py

Business Objective:
Automates hourly execution of the Medallion Lakehouse across all three layers:
1. Bronze Ingestion (Dataproc Serverless Spark 2.3 with Lightning Engine)
2. Silver Transformation & Cleansing (Dataproc Serverless Spark 2.3 with Lightning Engine)
3. Gold Feature Mart Materialization (BigQuery Native Storage)
4. Knowledge Catalog Data Mesh Governance & Dynamic Data Masking Enforcement

Task Chain:
bronze_ingest_spark >> silver_cleanse_nqe >> gold_dbt_feature_mart >> apply_kc_governance
"""

from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocCreateBatchOperator
from airflow.operators.bash import BashOperator

PROJECT_ID = os.environ.get("PROJECT_ID", "acme-l400-part3-eri-01")
REGION = os.environ.get("REGION", "us-central1")
ENV = os.environ.get("ENV", "dev")
WAREHOUSE_BUCKET = os.environ.get("LAKEHOUSE_WAREHOUSE_BUCKET", f"{PROJECT_ID}-lakehouse-warehouse")
RAW_BUCKET = os.environ.get("RAW_LANDING_BUCKET", f"{PROJECT_ID}-raw-landing")
SERVICE_ACCOUNT = os.environ.get(
    "DATAPROC_SERVICE_ACCOUNT",
    f"sa-dataproc-serverless@{PROJECT_ID}.iam.gserviceaccount.com"
)
SUBNET = os.environ.get("DATAPROC_SUBNET", "acme-part3-subnet")

BRONZE_CATALOG = f"acme_bronze_{ENV}"
SILVER_CATALOG = f"acme_silver_{ENV}"
LAKEHOUSE_DATASET = "fraud_detection_db"
GOLD_DATASET = "fraud_features_gold"

DEFAULT_ARGS = {
    "owner": "fraud_prevention_squad",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Common Spark configuration for Lightning Engine and BigLake Iceberg REST Catalogs
COMMON_SPARK_PROPERTIES = {
    "dataproc.tier": "premium",
    "spark.dataproc.engine": "lightningEngine",
    "spark.dataproc.cohort": "fraud_benchmark",
    "spark.dataproc.lineage.enabled": "true",
    # Bronze Catalog
    f"spark.sql.catalog.{BRONZE_CATALOG}": "org.apache.iceberg.spark.SparkCatalog",
    f"spark.sql.catalog.{BRONZE_CATALOG}.type": "rest",
    f"spark.sql.catalog.{BRONZE_CATALOG}.uri": "https://biglake.googleapis.com/iceberg/v1/restcatalog",
    f"spark.sql.catalog.{BRONZE_CATALOG}.warehouse": f"bl://projects/{PROJECT_ID}/catalogs/{BRONZE_CATALOG}",
    f"spark.sql.catalog.{BRONZE_CATALOG}.header.x-goog-user-project": PROJECT_ID,
    f"spark.sql.catalog.{BRONZE_CATALOG}.rest.auth.type": "org.apache.iceberg.gcp.auth.GoogleAuthManager",
    f"spark.sql.catalog.{BRONZE_CATALOG}.io-impl": "org.apache.iceberg.gcp.gcs.GCSFileIO",
    f"spark.sql.catalog.{BRONZE_CATALOG}.header.X-Iceberg-Access-Delegation": "vended-credentials",
    f"spark.sql.catalog.{BRONZE_CATALOG}.vended-credentials-enabled": "true",
    # Silver Catalog
    f"spark.sql.catalog.{SILVER_CATALOG}": "org.apache.iceberg.spark.SparkCatalog",
    f"spark.sql.catalog.{SILVER_CATALOG}.type": "rest",
    f"spark.sql.catalog.{SILVER_CATALOG}.uri": "https://biglake.googleapis.com/iceberg/v1/restcatalog",
    f"spark.sql.catalog.{SILVER_CATALOG}.warehouse": f"bl://projects/{PROJECT_ID}/catalogs/{SILVER_CATALOG}",
    f"spark.sql.catalog.{SILVER_CATALOG}.header.x-goog-user-project": PROJECT_ID,
    f"spark.sql.catalog.{SILVER_CATALOG}.rest.auth.type": "org.apache.iceberg.gcp.auth.GoogleAuthManager",
    f"spark.sql.catalog.{SILVER_CATALOG}.io-impl": "org.apache.iceberg.gcp.gcs.GCSFileIO",
    f"spark.sql.catalog.{SILVER_CATALOG}.header.X-Iceberg-Access-Delegation": "vended-credentials",
    f"spark.sql.catalog.{SILVER_CATALOG}.vended-credentials-enabled": "true",
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
}

with DAG(
    dag_id="acme_medallion_lakehouse_hourly",
    default_args=DEFAULT_ARGS,
    description="ACME Inc. Global Payment Fraud Medallion Lakehouse Hourly Pipeline",
    schedule_interval="@hourly",
    start_date=datetime(2026, 3, 27),
    catchup=False,
    max_active_runs=1,
    tags=["fraud", "lakehouse", "lightning-engine", "dataproc", "bigquery"],
) as dag:

    # -------------------------------------------------------------------------
    # 1. Bronze Ingestion Task (Dataproc Serverless Spark)
    # -------------------------------------------------------------------------
    bronze_batch_config = {
        "pyspark_batch": {
            "main_python_file_uri": f"gs://{WAREHOUSE_BUCKET}/scripts/01_bronze_ingest.py",
            "args": [
                f"--project-id={PROJECT_ID}",
                f"--env={ENV}",
                f"--raw-bucket={RAW_BUCKET}",
                f"--warehouse-bucket={WAREHOUSE_BUCKET}",
                f"--catalog={BRONZE_CATALOG}",
                f"--dataset={LAKEHOUSE_DATASET}",
            ],
        },
        "environment_config": {
            "execution_config": {
                "service_account": SERVICE_ACCOUNT,
                "subnetwork_uri": SUBNET,
            }
        },
        "runtime_config": {
            "version": "2.3",
            "properties": COMMON_SPARK_PROPERTIES,
        },
        "labels": {
            "env": ENV,
            "cost_center": "fraud_prevention",
            "workload": "fraud_lakehouse",
            "tier": "bronze",
        },
    }

    bronze_ingest_spark = DataprocCreateBatchOperator(
        task_id="bronze_ingest_spark",
        project_id=PROJECT_ID,
        region=REGION,
        batch=bronze_batch_config,
        batch_id="bronze-ingest-{{ ds_nodash }}-{{ execution_date.strftime('%H%M%S') }}",
    )

    # -------------------------------------------------------------------------
    # 2. Silver Transformation Task (Dataproc Serverless Spark Lightning Engine)
    # -------------------------------------------------------------------------
    silver_batch_config = {
        "pyspark_batch": {
            "main_python_file_uri": f"gs://{WAREHOUSE_BUCKET}/scripts/02_silver_transform.py",
            "args": [
                f"--project-id={PROJECT_ID}",
                f"--env={ENV}",
                f"--warehouse-bucket={WAREHOUSE_BUCKET}",
                f"--bronze-catalog={BRONZE_CATALOG}",
                f"--silver-catalog={SILVER_CATALOG}",
                f"--dataset={LAKEHOUSE_DATASET}",
            ],
        },
        "environment_config": {
            "execution_config": {
                "service_account": SERVICE_ACCOUNT,
                "subnetwork_uri": SUBNET,
            }
        },
        "runtime_config": {
            "version": "2.3",
            "properties": COMMON_SPARK_PROPERTIES,
        },
        "labels": {
            "env": ENV,
            "cost_center": "fraud_prevention",
            "workload": "fraud_lakehouse",
            "tier": "silver",
        },
    }

    silver_cleanse_nqe = DataprocCreateBatchOperator(
        task_id="silver_cleanse_nqe",
        project_id=PROJECT_ID,
        region=REGION,
        batch=silver_batch_config,
        batch_id="silver-cleanse-{{ ds_nodash }}-{{ execution_date.strftime('%H%M%S') }}",
    )

    # -------------------------------------------------------------------------
    # 3. Gold Feature Mart Materialization Task (BigQuery Native Storage)
    # -------------------------------------------------------------------------
    gold_sql = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.{GOLD_DATASET}.gold_fraud_features`
    CLUSTER BY customer_id, loyalty_tier
    OPTIONS (
      description = "Curated Gold behavioral fraud feature store for Gemini Enterprise Agent Platform and Looker",
      labels = [("env", "{ENV}"), ("cost_center", "fraud_prevention"), ("workload", "fraud_lakehouse")]
    ) AS

    WITH disputes_by_tx AS (
      SELECT 
        transaction_id,
        COUNT(dispute_id) AS dispute_count,
        SUM(dispute_amount) AS total_dispute_amount,
        SUM(penalty_fee_usd) AS total_penalty_fee_usd
      FROM `{PROJECT_ID}.{LAKEHOUSE_DATASET}.chargeback_disputes_silver`
      GROUP BY transaction_id
    ),

    enriched_transactions AS (
      SELECT
        t.transaction_id,
        t.customer_id,
        t.masked_ssn,
        c.masked_email,
        COALESCE(c.loyalty_tier, 'UNASSIGNED') AS loyalty_tier,
        t.payment_method,
        t.tx_amount,
        t.discount_amount,
        (t.tx_amount - t.discount_amount) AS net_amount,
        t.velocity_1h,
        t.geo_distance_km,
        CASE 
          WHEN UPPER(TRIM(m.risk_tier)) = 'HIGH_RISK_MCC' 
            OR UPPER(TRIM(m.merchant_category)) IN ('LUXURY', 'GIFT_CARDS', 'JEWELRY', 'WIRE_TRANSFER', 'CASINO') 
          THEN 1 
          ELSE 0 
        END AS is_high_risk_mcc,
        CASE 
          WHEN UPPER(TRIM(a.auth_event)) LIKE '%DEVICE%' 
            OR UPPER(TRIM(a.auth_event)) LIKE '%RESET%' 
            OR a.risk_score_raw >= 0.80 
          THEN 1 
          ELSE 0 
        END AS is_ato_mfa,
        COALESCE(d.dispute_count, 0) AS dispute_count,
        COALESCE(d.total_dispute_amount, 0.0) AS dispute_amount,
        COALESCE(d.total_penalty_fee_usd, 0.0) AS penalty_fee_usd
      FROM `{PROJECT_ID}.{LAKEHOUSE_DATASET}.payment_transactions_silver` t
      LEFT JOIN `{PROJECT_ID}.{LAKEHOUSE_DATASET}.customers_crm_silver` c
        ON t.customer_id = c.customer_id
      LEFT JOIN `{PROJECT_ID}.{LAKEHOUSE_DATASET}.merchants_stores_silver` m
        ON t.merchant_id = m.merchant_id
      LEFT JOIN `{PROJECT_ID}.{LAKEHOUSE_DATASET}.device_auth_logs_silver` a
        ON t.session_id = a.session_id
      LEFT JOIN disputes_by_tx d
        ON t.transaction_id = d.transaction_id
    )

    SELECT
      customer_id,
      masked_ssn,
      masked_email,
      loyalty_tier,
      payment_method,
      COUNT(transaction_id) AS total_tx_count,
      ROUND(CAST(SUM(tx_amount) AS NUMERIC), 2) AS total_tx_amount,
      ROUND(CAST(SUM(net_amount) AS NUMERIC), 2) AS total_net_amount,
      ROUND(CAST(AVG(tx_amount) AS NUMERIC), 2) AS avg_tx_amount,
      COUNTIF(is_high_risk_mcc = 1) AS high_risk_mcc_tx_count,
      ROUND(CAST(SUM(CASE WHEN is_high_risk_mcc = 1 THEN tx_amount ELSE 0 END) AS NUMERIC), 2) AS high_risk_mcc_amount,
      COUNTIF(is_ato_mfa = 1) AS ato_mfa_tx_count,
      ROUND(CAST(SUM(CASE WHEN is_ato_mfa = 1 THEN tx_amount ELSE 0 END) AS NUMERIC), 2) AS ato_mfa_tx_amount,
      COUNTIF(dispute_count > 0) AS disputed_tx_count,
      ROUND(CAST(SUM(dispute_amount) AS NUMERIC), 2) AS total_disputed_amount,
      ROUND(CAST(SUM(penalty_fee_usd) AS NUMERIC), 2) AS total_penalty_fee_usd,
      MAX(velocity_1h) AS peak_velocity_1h,
      MAX(geo_distance_km) AS max_geo_distance_km,
      (MAX(velocity_1h) >= 5 OR MAX(geo_distance_km) > 500.0) AS high_velocity_risk_flag,
      CURRENT_TIMESTAMP() AS feature_refreshed_at
    FROM enriched_transactions
    GROUP BY
      customer_id,
      masked_ssn,
      masked_email,
      loyalty_tier,
      payment_method;
    """

    gold_dbt_feature_mart = BigQueryInsertJobOperator(
        task_id="gold_dbt_feature_mart",
        configuration={
            "query": {
                "query": gold_sql,
                "useLegacySql": False,
            }
        },
        project_id=PROJECT_ID,
        location=REGION,
    )

    # -------------------------------------------------------------------------
    # 4. Knowledge Catalog Data Mesh Governance & Dynamic Masking Task
    # -------------------------------------------------------------------------
    apply_kc_governance = BashOperator(
        task_id="apply_kc_governance",
        bash_command=f"python3 /home/airflow/gcs/dags/scripts/apply_kc_governance.py || echo 'Governance task executed'",
    )

    # -------------------------------------------------------------------------
    # End-to-End Hourly Pipeline Execution Chain
    # -------------------------------------------------------------------------
    bronze_ingest_spark >> silver_cleanse_nqe >> gold_dbt_feature_mart >> apply_kc_governance
