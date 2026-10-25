# Technical Specification & Schema Mapping Manifesto (`SPEC.md`) — Medallion Fraud Lakehouse

## 0. Document Control, Architecture Overview & Step 04 Target File Tree
### 0.1 Specification Purpose & Traceability
- **Upstream Inputs:** `docs/part3/DISCOVERY.md` & `docs/part3/EDA.md`
- **Target Project, Region & Lifecycle Stage:** `<TODO: project_id>` • `<TODO: region (default: us-central1)>` • `ENV = dev`
### 0.2 End-to-End Medallion Lakehouse Architecture Diagram
- (Provide a Mermaid flowchart showing Raw Landing -> Bronze Catalog -> Silver Catalog -> BigQuery External Registration -> Gold Feature Mart -> Knowledge Catalog & Composer)
### 0.3 Step 04 Target Workspace File Tree (`docs/part3/` & `src/part3/`)
```text
src/part3/
├── dq_rules.yaml
├── scripts/
│   ├── 01_bronze_ingest.py
│   ├── 02_silver_transform.py
│   ├── register_bq_external_tables.py
│   └── apply_kc_governance.py
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/gold_fraud_features.sql
├── sql/
│   ├── gold_fraud_features.sql
│   └── reconcile_silver_vs_gold.sql
└── dags/
    └── medallion_lakehouse_dag.py
```

## 1. Environment & Pre-Provisioned Infrastructure Bindings (Phase 1 Contract)
### 1.1 Project, Network, Identity & FinOps Attribution Contract
- (Specify VPC, subnet with PGA, execution service account, and FinOps billing labels)
### 1.2 Storage Buckets & BigQuery Datasets Inventory
- (Specify raw landing bucket, warehouse bucket prefixes, Spark event log bucket, and target BigQuery datasets)
### 1.3 Dual Google Lakehouse Iceberg REST Catalogs & Credential Vending Contract
- (Specify Bronze and Silver REST catalog names, `bl://` warehouse URIs, `lakehouse-vending-conn` connection, and Spark REST catalog properties)

## 2. Table-by-Table Semantic Schema Mapping Manifesto (`@skill:schema-mapping`)
### 2.1 End-to-End Column & Row Progression Summary (`Raw` -> `Bronze` -> `Silver` -> `Gold`)
| Table / Layer | Raw Input | Bronze Table | Silver Table | Target Row / Column Contract |
| :--- | :--- | :--- | :--- | :--- |
| `customers_crm` .. `gold_fraud_features` | <TODO> | <TODO> | <TODO> | <TODO> |
### 2.2 Mapping Manifesto 1: `customers_crm` (`Raw` -> `customers_crm_bronze` -> `customers_crm_silver`)
| Source Column | Target Column | Target Type | Transformation / Hygiene Rule | Null & PII Policy |
| :--- | :--- | :--- | :--- | :--- |
| <TODO: map all columns> | <TODO> | <TODO> | <TODO> | <TODO> |
### 2.3 Mapping Manifesto 2: `merchants_stores` (`Raw` -> `merchants_stores_bronze` -> `merchants_stores_silver`)
- (Complete column-by-column mapping table including multi-line CSV notes, decimal casting, and category normalization)
### 2.4 Mapping Manifesto 3: `device_auth_logs` (`Raw` -> `device_auth_logs_bronze` -> `device_auth_logs_silver`)
- (Complete column-by-column mapping table including `auth_event` punctuation stripping and latency/risk casting)
### 2.5 Mapping Manifesto 4: `payment_transactions` (`Raw` -> `payment_transactions_bronze` -> `payment_transactions_silver`)
- (Complete column-by-column mapping table including SHA-256 `masked_ssn` with raw `ssn` dropped, `net_amount_after_discount`, `geo_distance_km`, and `velocity_1h`)
### 2.6 Mapping Manifesto 5: `chargeback_disputes` (`Raw` -> `chargeback_disputes_bronze` -> `chargeback_disputes_silver`)
- (Complete column-by-column mapping table including `reason_code` normalization and `penalty_fee_usd` coalescing)
### 2.7 Mapping Manifesto 6: `fraud_features_gold.gold_fraud_features` (`5 Silver Tables` -> `Gold Feature Store`)
- (Complete mapping table for all required Gold columns, grouping keys, pre-aggregated dispute metrics, and risk flags)

## 3. Bronze Layer Specification (`src/part3/scripts/01_bronze_ingest.py` — Phase 2 Contract)
### 3.1 Runtime & Engine Configuration
- (Dataproc Serverless runtime version, tier, Lightning Engine native runtime flags, and OpenLineage properties)
### 3.2 Source-to-Target Ingestion Contract
- (Explicit all-`StringType` schemas per feed, `mode='PERMISSIVE'`, multi-line CSV reader options, `_ingestion_timestamp`, `_source_file`, and Iceberg V2 table properties)

## 4. Silver Layer Specification (`src/part3/scripts/02_silver_transform.py` — Phases 3 & 4 Contract)
### 4.1 Runtime & Engine Configuration (NQE Velox C++ SIMD + Iceberg V2 Merge-on-Read)
- (Dual catalog session config, ANSI mode, and Iceberg V2 `merge-on-read` table properties)
### 4.2 Vectorized Cleansing Helper Specifications
- (Pure Spark SQL / Velox expressions—zero Python UDFs—for key normalization, accounting-negative numeric parsing, `DECIMAL(18, 2)` / `BIGINT` / `DOUBLE` casting, and multi-format timestamp parsing)
### 4.3 Per-Table Filter Predicates, Deduplication Windows & Financial Baselines
- (Exact mandatory filter predicates preserving Class N4 benign nulls, and `ROW_NUMBER()` window tie-breakers per table)
### 4.4 Engineered Fraud Features & Cryptographic PII De-Identification
- (Formulas for `masked_ssn` and `masked_email` with cleartext `ssn`/`email` dropped, `net_amount_after_discount`, clamped Haversine `geo_distance_km`, and 1-hour sliding `velocity_1h`)

## 5. BigQuery Iceberg Registration & Gold Layer Specification (`src/part3/dbt_project/` — Phase 5 Contract)
### 5.1 Zero-Copy External Table Registration (`src/part3/scripts/register_bq_external_tables.py`)
- (`CREATE OR REPLACE EXTERNAL TABLE` DDL pattern using `lakehouse-vending-conn` for all Bronze and Silver Iceberg tables)
### 5.2 Gold Layer `dbt` Project Architecture (`src/part3/dbt_project/` & `src/part3/sql/gold_fraud_features.sql`)
- (`dbt_project.yml`, `profiles.yml`, `disputes_by_tx` pre-aggregation CTE, 5-table join logic, `CLUSTER BY customer_id, loyalty_tier`, and `COALESCE(loyalty_tier, 'UNASSIGNED')`)

## 6. Cross-Engine Zero-Copy Reconciliation (`src/part3/sql/reconcile_silver_vs_gold.sql` — Phase 6 Contract)
### 6.1 Reconciliation Query Contract
- (SQL reconciliation query comparing Silver Iceberg vs. Gold Native Storage by `payment_method` and asserting zero row/dollar variance)

## 7. Knowledge Catalog Governance, Policy Tags & Auto DQ (`src/part3/scripts/apply_kc_governance.py` & `src/part3/dq_rules.yaml` — Phase 7 Contract)
### 7.1 Bronze Policy Tag Taxonomy & SHA-256 Dynamic Data Masking
- (Taxonomy, policy tag, and Data Policy bindings on Bronze `ssn` columns)
### 7.2 Knowledge Catalog Aspect Type & Multi-Table Metadata Attachment
- (`medallion-governance-template` aspect fields attached across all Bronze, Silver, and Gold tables)
### 7.3 Knowledge Catalog Data Mesh Domain & Data Product
- (Domain lake, curated zone, and Data Product resource identifiers)
### 7.4 Automated Data Quality Scan (`src/part3/dq_rules.yaml`)
- (Data Quality scan identifier and YAML rule definitions over `gold_fraud_features`)

## 8. Cloud Composer 3 Orchestration Specification (`src/part3/dags/medallion_lakehouse_dag.py` — Phase 7 Contract)
### 8.1 DAG Configuration & Best Practices
- (DAG ID, schedule, SLA/retry settings, FinOps labels, 4-task dependency chain, and GCS staging path)

## 9. Acceptance Verification Rubric & Step 04–08 Execution Sequence
### 9.1 Complete 7-Phase Automated Grading Matrix (`run-all-evals.sh`)
- (Summary table mapping Phases 1–7 to expected verification metrics)
### 9.2 Deterministic Execution Sequence for Steps 04–08
- (Step-by-step execution order from catalog provisioning through Bronze, Silver, BigQuery registration, Gold dbt build, reconciliation, governance, and final evaluation)
