# DESIGN-05: Automated Verification & CI/CD Promotion Gates

## 1. Business Objective
Implement automated quality verification gates that must pass with 100% compliance before promoting the lakehouse pipelines from `dev` to `qa` and `prod`.

## 2. Technical Specifications & Promotion Gates

### 2.1 Gate 1: Dataplex Auto Data Quality Scan (`src/governance/dq_rules.yaml`)
* **Scan Identifier:** `fraud-gold-dq-scan-dev`
* **Target Table:** `fraud_features_gold.gold_fraud_features`
* **Rule Definitions:**
  1. `customer_id IS NOT NULL` (Completeness = 100%)
  2. `REGEXP_CONTAINS(masked_ssn, r'^[0-9a-f]{64}$')` (Cryptographic compliance)
  3. `REGEXP_CONTAINS(masked_email, r'^[0-9a-f]{64}$')` (Cryptographic compliance)
  4. `total_tx_amount > 0` (Spend positivity for active customers)
  5. `total_tx_count > 0` (Transaction positivity for active customers)
  6. `payment_method IN (0, 1, 2)` (Valid categorical domain)
  7. `total_net_amount <= total_tx_amount` (Net amount constraint)
  8. `high_risk_mcc_amount <= total_tx_amount` (Sub-metric constraint)
  9. `total_disputed_amount <= total_tx_amount` (Dispute boundary constraint)
  10. `peak_velocity_1h >= 1` (Frequency constraint)
  11. `max_geo_distance_km >= 0` (Non-negative distance)

### 2.2 Gate 2: Cross-Engine Financial Reconciliation (`src/sql/reconcile_silver_vs_gold.sql`)
* **Objective:** Compare upstream Silver transactions against downstream Gold aggregated features.
* **Tolerance:** Exactly **$0.00 dollar variance** and **0 row variance**.
* **Target Benchmarks:**
  * Total transactions: 10,000,000
  * Gross Dollar Volume: $8,069,098,864.39
  * Net Dollar Volume: $8,059,136,414.39
  * Total Disputed Volume: $598,467,476.02
  * Per-Payment Breakdown:
    * Credit (`0`): $2,434,254,756.10
    * Debit (`1`): $2,439,184,262.09
    * Mobile Wallet (`2`): $3,195,659,846.20

### 2.3 Automated Test Suite (`evals/prompts.json` and unit tests)
Automated verification fixtures validating:
* Bronze row counts (15,506,500 rows across 5 tables)
* Silver clean row counts (14,875,000 rows across 5 tables)
* Gold curated row counts (518,638 rows across 233,945 customers)
* Zero PII leakage in Silver and Gold
* Cloud Composer DAG parseability

## 3. Acceptance Criteria
1. Gate 1 passes with 100% of rules evaluated successfully.
2. Gate 2 returns 0 rows with non-zero variance.
3. Automated unit/eval tests pass locally.
