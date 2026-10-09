# DESIGN-02: Data Layer (Bronze Ingestion & Silver Cleansing)

## 1. Business Objective
Design and implement the high-throughput, loss-free Bronze ingestion and the SIMD-accelerated, high-precision Silver cleansing pipelines for ACME's 5 source data feeds on Dataproc Serverless Spark 2.3 with Lightning Engine (`spark.dataproc.engine=lightningEngine`).

## 2. Technical Specifications & Contracts

### 2.1 Bronze Tier Ingestion (`src/pipelines/01_bronze_ingest.py`)
* **Raw Feeds:** 15,506,500 total records from `gs://acme-l400-part3-eri-01-raw-landing/v0.01/`:
  1. `customers_crm`: 510,000 JSONL records (`snapshot_date=2026-03-27`)
  2. `merchants_stores`: 26,000 CSV records (`snapshot_date=2026-03-27`, multiLine=true, escape="\"")
  3. `device_auth_logs`: 4,120,000 JSONL records (`year=2026/month=03/day={25,26,27}`)
  4. `payment_transactions`: 10,490,000 JSONL records (`year=2026/month=03/day={25,26,27}`)
  5. `chargeback_disputes`: 360,500 JSONL records (`year=2026/month=03/day={25,26,27}`)
* **Schema Contract:** Permissive all-`StringType` schema to guarantee 100% loss-free capture of dirty/corrupted rows.
* **Audit Metadata:** Append `_ingestion_timestamp` (`TIMESTAMP`) and `_source_file` (`STRING`).
* **Storage Target:** Apache Iceberg V2 tables in `acme_bronze_dev.fraud_detection_db.*_bronze`.

### 2.2 Silver Tier Cleansing (`src/pipelines/02_silver_transform.py`)
* **Clean Row Target:** Exactly 14,875,000 unique records:
  * `customers_crm_silver`: 500,000 rows
  * `merchants_stores_silver`: 25,000 rows
  * `device_auth_logs_silver`: 4,000,000 rows
  * `payment_transactions_silver`: 10,000,000 rows
  * `chargeback_disputes_silver`: 350,000 rows
* **4-Class Null Contract:**
  * Drop 119,000 corrupt rows across Classes N1, N2, N3a (missing PK/FK/timestamp), and N3b (non-positive metric amounts/fees/latencies).
  * Preserve 2,750,000 Class N4 benign nulls in optional attributes.
* **Vectorized Sanitization (Velox SIMD compliant, zero Python UDFs):**
  * Strip currency symbols (`$`, `USD`), commas (`,`), unit labels, and footnote noise (`*`, `#`, `!`, `~`).
  * Reverse 9,094 accounting parentheses `($49.99)` -> `-49.99`.
  * Safe casting via `try_cast`.
* **Key Normalization & Deduplication:**
  * Clean PK/FK: `UPPER(TRIM(regexp_replace(k, r'[\s\u00a0\u200b\*#!~]+', '')))`.
  * Window deduplication: `ROW_NUMBER() OVER (PARTITION BY pk ORDER BY event_timestamp DESC) = 1` removing 512,500 duplicates (including 420,000 `TIMEOUT_RETRY` transactions).
* **Behavioral Enrichment:**
  * Haversine spherical distance: `geo_distance_km`.
  * 1-hour transaction frequency: `velocity_1h`.
* **Cryptographic PII Pseudonymization & De-identification:**
  * Irreversible lowercase hex SHA-256: `masked_ssn = sha2(regexp_replace(trim(ssn), '[^0-9]', ''), 256)` and `masked_email = sha2(lower(trim(email)), 256)`.
  * Mandatory: Completely drop raw `ssn` and `email` columns.
* **Storage Target:** Apache Iceberg V2 Merge-on-Read (MoR) tables in `acme_silver_dev.fraud_detection_db.*_silver`.

## 3. Acceptance Criteria
1. Bronze tables contain exactly 15,506,500 total rows.
2. Silver tables contain exactly 14,875,000 total rows.
3. Zero cleartext `ssn` or `email` columns exist in any Silver table.
4. Accounting parentheses correctly yield negative amounts in Silver.
