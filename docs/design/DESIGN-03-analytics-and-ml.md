# DESIGN-03: Analytics & ML Feature Store (Gold Layer)

## 1. Business Objective
Deliver a curated, zero-fan-out feature mart in BigQuery Native Storage (`fraud_features_gold.gold_fraud_features`) that feeds downstream fraud inference models, the Gemini Enterprise Agent Platform, and Looker dashboards with exact financial reconciliation back to Silver source data.

## 2. Technical Specifications & Architecture

### 2.1 Storage & Layout
* **Target Table:** `fraud_features_gold.gold_fraud_features`
* **Storage Engine:** BigQuery Native Storage
* **Physical Layout:** `CLUSTER BY customer_id, loyalty_tier`
* **Grain:** `(customer_id, masked_ssn, masked_email, COALESCE(loyalty_tier, 'UNASSIGNED'), payment_method)`
* **Target Record Count:** 518,638 curated feature rows across 233,945 active customers.

### 2.2 Pre-Aggregated Disputes CTE Pattern (Zero Fan-Out Guarantee)
Because transactions can have multiple dispute filings (up to 4 partial chargebacks per transaction), joining disputes directly to transactions causes Cartesian explosion. The model MUST aggregate disputes first:
```sql
WITH disputes_by_tx AS (
  SELECT 
    transaction_id,
    COUNT(dispute_id) AS dispute_count,
    SUM(dispute_amount) AS total_dispute_amount,
    SUM(penalty_fee_usd) AS total_penalty_fee_usd
  FROM `acme-l400-part3-eri-01.fraud_detection_db.chargeback_disputes_silver`
  GROUP BY transaction_id
)
```

### 2.3 Curated 20-Column Schema
1. `customer_id` (STRING)
2. `masked_ssn` (STRING - 64 hex chars)
3. `masked_email` (STRING - 64 hex chars)
4. `loyalty_tier` (STRING - coalesced to 'UNASSIGNED')
5. `payment_method` (INT64 - 0=Credit, 1=Debit, 2=Wallet)
6. `total_tx_count` (INT64)
7. `total_tx_amount` (NUMERIC(14,2))
8. `total_net_amount` (NUMERIC(14,2))
9. `avg_tx_amount` (NUMERIC(10,2))
10. `high_risk_mcc_tx_count` (INT64)
11. `high_risk_mcc_amount` (NUMERIC(14,2))
12. `ato_mfa_tx_count` (INT64)
13. `ato_mfa_tx_amount` (NUMERIC(14,2))
14. `disputed_tx_count` (INT64)
15. `total_disputed_amount` (NUMERIC(14,2))
16. `total_penalty_fee_usd` (NUMERIC(10,2))
17. `peak_velocity_1h` (INT64)
18. `max_geo_distance_km` (FLOAT64)
19. `high_velocity_risk_flag` (BOOLEAN)
20. `feature_refreshed_at` (TIMESTAMP)

### 2.4 Financial Reconciliation Totals
* **Total Transactions:** 10,000,000
* **Gross Spend:** $8,069,098,864.39
* **Net Spend:** $8,059,136,414.39
* **Total Disputed:** $598,467,476.02
* **Payment Methods Breakdown:**
  * Credit (`0`): $2,434,254,756.10
  * Debit (`1`): $2,439,184,262.09
  * Mobile Wallet (`2`): $3,195,659,846.20

## 3. Acceptance Criteria
1. Exactly 518,638 rows materialized in `fraud_features_gold.gold_fraud_features`.
2. Cross-engine financial reconciliation against Silver achieves $0.00 variance across Credit, Debit, and Wallet.
3. High-velocity burst accounts (`peak_velocity_1h >= 5 OR max_geo_distance_km > 500.0`) flagged accurately.
