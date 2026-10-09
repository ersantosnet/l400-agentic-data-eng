-- =============================================================================
-- ACME Global Payment Fraud Lakehouse - Cross-Engine Financial Reconciliation
-- Step 05 / Step 08 Production SQL: reconcile_silver_vs_gold.sql
--
-- Objective:
-- Assert penny-exact financial reconciliation ($0.00 dollar variance and 0 row
-- variance) between upstream Silver settled transactions and downstream Gold feature mart.
-- =============================================================================

WITH silver_summary AS (
  SELECT
    t.payment_method,
    COUNT(t.transaction_id) AS silver_tx_count,
    ROUND(CAST(SUM(t.tx_amount) AS NUMERIC), 2) AS silver_gross_amount,
    ROUND(CAST(SUM(COALESCE(t.net_amount_after_discount, t.tx_amount - t.discount_amount)) AS NUMERIC), 2) AS silver_net_amount,
    ROUND(CAST(SUM(COALESCE(d.total_dispute_amount, 0)) AS NUMERIC), 2) AS silver_disputed_amount
  FROM `acme-l400-part3-eri-01.fraud_detection_db.payment_transactions_silver` t
  LEFT JOIN (
    SELECT 
      transaction_id, 
      SUM(dispute_amount) AS total_dispute_amount 
    FROM `acme-l400-part3-eri-01.fraud_detection_db.chargeback_disputes_silver`
    GROUP BY transaction_id
  ) d ON t.transaction_id = d.transaction_id
  GROUP BY t.payment_method
),

gold_summary AS (
  SELECT
    payment_method,
    SUM(total_tx_count) AS gold_tx_count,
    ROUND(CAST(SUM(total_tx_amount) AS NUMERIC), 2) AS gold_gross_amount,
    ROUND(CAST(SUM(total_net_amount) AS NUMERIC), 2) AS gold_net_amount,
    ROUND(CAST(SUM(total_disputed_amount) AS NUMERIC), 2) AS gold_disputed_amount
  FROM `acme-l400-part3-eri-01.fraud_features_gold.gold_fraud_features`
  GROUP BY payment_method
),

reconciliation_by_method AS (
  SELECT
    CASE s.payment_method
      WHEN 0 THEN 'Credit (0)'
      WHEN 1 THEN 'Debit (1)'
      WHEN 2 THEN 'Mobile Wallet (2)'
      ELSE 'Unknown'
    END AS payment_method_name,
    s.payment_method,
    s.silver_tx_count,
    g.gold_tx_count,
    (g.gold_tx_count - s.silver_tx_count) AS tx_count_variance,
    s.silver_gross_amount,
    g.gold_gross_amount,
    (g.gold_gross_amount - s.silver_gross_amount) AS gross_amount_variance,
    s.silver_net_amount,
    g.gold_net_amount,
    (g.gold_net_amount - s.silver_net_amount) AS net_amount_variance,
    s.silver_disputed_amount,
    g.gold_disputed_amount,
    (g.gold_disputed_amount - s.silver_disputed_amount) AS disputed_amount_variance,
    CASE 
      WHEN (g.gold_tx_count - s.silver_tx_count) = 0 
       AND (g.gold_gross_amount - s.silver_gross_amount) = 0.00
       AND (g.gold_net_amount - s.silver_net_amount) = 0.00
       AND (g.gold_disputed_amount - s.silver_disputed_amount) = 0.00
      THEN 'PASS (EXACT RECONCILIATION)'
      ELSE 'FAIL (VARIANCE DETECTED)'
    END AS status
  FROM silver_summary s
  FULL OUTER JOIN gold_summary g
    ON s.payment_method = g.payment_method
),

totals_summary AS (
  SELECT
    'TOTAL / ALL' AS payment_method_name,
    -1 AS payment_method,
    SUM(silver_tx_count) AS silver_tx_count,
    SUM(gold_tx_count) AS gold_tx_count,
    SUM(tx_count_variance) AS tx_count_variance,
    SUM(silver_gross_amount) AS silver_gross_amount,
    SUM(gold_gross_amount) AS gold_gross_amount,
    SUM(gross_amount_variance) AS gross_amount_variance,
    SUM(silver_net_amount) AS silver_net_amount,
    SUM(gold_net_amount) AS gold_net_amount,
    SUM(net_amount_variance) AS net_amount_variance,
    SUM(silver_disputed_amount) AS silver_disputed_amount,
    SUM(gold_disputed_amount) AS gold_disputed_amount,
    SUM(disputed_amount_variance) AS disputed_amount_variance,
    CASE 
      WHEN SUM(tx_count_variance) = 0 
       AND SUM(gross_amount_variance) = 0.00
       AND SUM(net_amount_variance) = 0.00
       AND SUM(disputed_amount_variance) = 0.00
      THEN 'PASS (EXACT RECONCILIATION)'
      ELSE 'FAIL (VARIANCE DETECTED)'
    END AS status
  FROM reconciliation_by_method
)

SELECT * FROM reconciliation_by_method
UNION ALL
SELECT * FROM totals_summary
ORDER BY payment_method;
