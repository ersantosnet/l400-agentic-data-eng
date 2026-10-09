{{ config(
    materialized='table',
    cluster_by=["customer_id", "loyalty_tier"],
    labels={
        'env': 'dev',
        'cost_center': 'fraud_prevention',
        'workload': 'fraud_lakehouse'
    }
) }}

WITH disputes_by_tx AS (
  -- PRE-AGGREGATION CTE: Eliminates Cartesian fan-out from 1-to-N disputes per transaction
  SELECT 
    transaction_id,
    COUNT(dispute_id) AS dispute_count,
    SUM(dispute_amount) AS total_dispute_amount,
    SUM(penalty_fee_usd) AS total_penalty_fee_usd
  FROM {{ source('acme_silver_dev', 'chargeback_disputes_silver') }}
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
  FROM {{ source('acme_silver_dev', 'payment_transactions_silver') }} t
  LEFT JOIN {{ source('acme_silver_dev', 'customers_crm_silver') }} c
    ON t.customer_id = c.customer_id
  LEFT JOIN {{ source('acme_silver_dev', 'merchants_stores_silver') }} m
    ON t.merchant_id = m.merchant_id
  LEFT JOIN {{ source('acme_silver_dev', 'device_auth_logs_silver') }} a
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
  payment_method
