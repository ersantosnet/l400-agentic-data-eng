# DESIGN-04: Orchestration & Governance Layer

## 1. Business Objective
Automate the end-to-end Medallion Lakehouse execution on Cloud Composer 3 and enforce Data Mesh Pattern 2 governance across all 11 BigQuery assets with Dataplex Knowledge Catalog, OpenLineage observability, and Dynamic Data Masking.

## 2. Technical Specifications & Architecture

### 2.1 Cloud Composer 3 Orchestration (`src/orchestration/medallion_lakehouse_dag.py`)
* **Schedule:** Hourly (`@hourly`)
* **Staging Path:** `gs://acme-l400-part3-eri-01-lakehouse-warehouse/dags/medallion_lakehouse_dag.py`
* **Task Dependency Chain:**
  ```python
  bronze_ingest_spark >> silver_cleanse_nqe >> gold_dbt_feature_mart >> apply_kc_governance
  ```
* **Tasks Description:**
  1. `bronze_ingest_spark`: Submits `01_bronze_ingest.py` as a Dataproc Serverless Spark batch.
  2. `silver_cleanse_nqe`: Submits `02_silver_transform.py` with Lightning Engine enabled (`spark.dataproc.engine=lightningEngine`, `spark.dataproc.cohort=fraud_benchmark`).
  3. `gold_dbt_feature_mart`: Executes BigQuery native transformation for `fraud_features_gold.gold_fraud_features`.
  4. `apply_kc_governance`: Runs `apply_kc_governance.py` to ensure Data Mesh domains, products, policy tags, and aspect cards are active.
* **Lineage:** `spark.dataproc.lineage.enabled=true` automatically emits OpenLineage events to Cloud Knowledge Catalog.

### 2.2 Data Mesh Pattern 2 Governance (`src/governance/apply_kc_governance.py`)
* **Domain:** `FraudDomain` (`fraud-domain`)
* **Subdomains:** `Fraud/Bronze` and `Fraud/Silver`
* **Data Product:** `FraudRiskFeatureStore` (`fraud-risk-feature-store`) with an Hourly Freshness SLA.
* **Governance Card Aspect:** `medallion-governance-template` attached to all 11 BigQuery entries:
  * `data_steward`: `dpatel@acme.com`
  * `pii_classification`: `restricted_confidential`
  * `medallion_tier`: `BRONZE`, `SILVER`, or `GOLD`
  * `sla_freshness_hours`: `1` (`sla_freshness='HOURLY'`)
  * `lifecycle_env`: `'DEV'`
  * `ssn_masked`: `BOOLEAN` (False for 5 Bronze tables, True for 5 Silver and 1 Gold table)
* **Policy Tags & Masking:**
  * Taxonomy: `pii_taxonomy`
  * Tag: `SSN_Cardholder` (`FINE_GRAINED_ACCESS_CONTROL`)
  * Dynamic Masking: BigQuery `SHA256` masking attached to Bronze SSN columns (`customers_crm_bronze.ssn`, `payment_transactions_bronze.ssn`).

## 3. Acceptance Criteria
1. Cloud Composer DAG successfully scheduled and parsed without Airflow syntax or import errors.
2. Dataplex Domain and Data Product registered with all 11 BigQuery entries linked.
3. Aspect metadata attached to all 11 entries with correct tier and masking status.
