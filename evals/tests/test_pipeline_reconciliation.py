#!/usr/bin/env python3
"""
Automated Verification Suite for Step 08: Zero-Copy Data Quality & Financial Reconciliation
File: evals/tests/test_pipeline_reconciliation.py
"""

import json
import subprocess
import unittest


class TestPipelineReconciliation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open("agent-config.json", "r") as f:
            cls.config = json.load(f)
        cls.project_id = cls.config["gcp-project-id"]
        cls.lakehouse_ds = cls.config["bigquery-lakehouse-dataset"]
        cls.gold_ds = cls.config["bigquery-gold-dataset"]

    def run_bq_query(self, query: str):
        cmd = ["bq", "query", "--use_legacy_sql=false", "--format=json"]
        proc = subprocess.run(cmd, input=query, text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)

    def test_01_biglake_tables_registered(self):
        """Verify all 10 BigLake Iceberg external tables are registered and accessible."""
        expected_tables = [
            "customers_crm_bronze",
            "merchants_stores_bronze",
            "device_auth_logs_bronze",
            "payment_transactions_bronze",
            "chargeback_disputes_bronze",
            "customers_crm_silver",
            "merchants_stores_silver",
            "device_auth_logs_silver",
            "payment_transactions_silver",
            "chargeback_disputes_silver",
        ]
        query = f"""
        SELECT table_name, table_type
        FROM `{self.project_id}.{self.lakehouse_ds}.INFORMATION_SCHEMA.TABLES`
        """
        rows = self.run_bq_query(query)
        found_tables = {r["table_name"] for r in rows}
        for tbl in expected_tables:
            self.assertIn(tbl, found_tables, f"Missing BigLake table: {tbl}")

    def test_02_gold_fraud_features_grain_and_clustering(self):
        """Verify Gold fraud features table exists, row count matches expected grain."""
        query = f"""
        SELECT 
          COUNT(*) AS total_rows,
          COUNT(DISTINCT customer_id) AS distinct_customers
        FROM `{self.project_id}.{self.gold_ds}.gold_fraud_features`
        """
        rows = self.run_bq_query(query)
        self.assertEqual(len(rows), 1)
        total_rows = int(rows[0]["total_rows"])
        distinct_customers = int(rows[0]["distinct_customers"])
        # Expected ~518,639 feature rows across 233,945 customers
        self.assertAlmostEqual(total_rows, 518639, delta=5)
        self.assertEqual(distinct_customers, 233945)

    def test_03_zero_cleartext_pii_in_silver_and_gold(self):
        """Verify strict privacy enforcement: NO raw ssn or email in Silver or Gold schemas."""
        for ds, tbl in [
            (self.lakehouse_ds, "customers_crm_silver"),
            (self.lakehouse_ds, "payment_transactions_silver"),
            (self.gold_ds, "gold_fraud_features"),
        ]:
            query = f"""
            SELECT column_name
            FROM `{self.project_id}.{ds}.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name = '{tbl}' AND column_name IN ('ssn', 'email')
            """
            rows = self.run_bq_query(query)
            self.assertEqual(
                len(rows), 0,
                f"PRIVACY VIOLATION: Raw cleartext PII found in {ds}.{tbl}: {[r['column_name'] for r in rows]}"
            )

    def test_04_cross_engine_financial_reconciliation(self):
        """Assert penny-exact financial reconciliation ($0.00 dollar variance, 0 row variance)."""
        with open("src/sql/reconcile_silver_vs_gold.sql", "r") as f:
            query = f.read()
        rows = self.run_bq_query(query)
        self.assertGreaterEqual(len(rows), 4, "Expected at least 3 payment methods + total summary")
        
        for r in rows:
            method = r["payment_method_name"]
            status = r["status"]
            tx_var = int(r["tx_count_variance"])
            gross_var = float(r["gross_amount_variance"])
            net_var = float(r["net_amount_variance"])
            disp_var = float(r["disputed_amount_variance"])
            self.assertEqual(
                status, "PASS (EXACT RECONCILIATION)",
                f"Financial variance detected in {method}: tx_var={tx_var}, gross_var={gross_var}, net_var={net_var}, disp_var={disp_var}"
            )
            self.assertEqual(tx_var, 0, f"Row variance in {method}")
            self.assertAlmostEqual(gross_var, 0.0, places=2, msg=f"Gross dollar variance in {method}")
            self.assertAlmostEqual(net_var, 0.0, places=2, msg=f"Net dollar variance in {method}")
            self.assertAlmostEqual(disp_var, 0.0, places=2, msg=f"Disputed dollar variance in {method}")

    def test_05_data_quality_rules_100_percent_pass(self):
        """Verify all 12 DQ rules on gold_fraud_features pass with 100.0% adherence."""
        query = f"""
        SELECT
          COUNT(*) AS total_rows,
          COUNTIF(customer_id IS NOT NULL) AS rule_1,
          COUNTIF(REGEXP_CONTAINS(masked_ssn, r'^[0-9a-f]{{64}}$')) AS rule_2,
          COUNTIF(REGEXP_CONTAINS(masked_email, r'^[0-9a-f]{{64}}$')) AS rule_3,
          COUNTIF(loyalty_tier IS NOT NULL) AS rule_4,
          COUNTIF(payment_method IN (0, 1, 2)) AS rule_5,
          COUNTIF(total_tx_amount > 0) AS rule_6,
          COUNTIF(total_tx_count > 0) AS rule_7,
          COUNTIF(total_net_amount <= total_tx_amount) AS rule_8,
          COUNTIF(high_risk_mcc_amount <= total_tx_amount) AS rule_9,
          COUNTIF(total_disputed_amount >= 0) AS rule_10,
          COUNTIF(max_geo_distance_km >= 0.0) AS rule_11,
          COUNTIF(peak_velocity_1h >= 1) AS rule_12
        FROM `{self.project_id}.{self.gold_ds}.gold_fraud_features`
        """
        rows = self.run_bq_query(query)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        total = int(r["total_rows"])
        for i in range(1, 13):
            passed = int(r[f"rule_{i}"])
            self.assertEqual(
                passed, total,
                f"Rule {i} failed DQ gate: {passed}/{total} ({passed/total*100:.2f}%)"
            )


if __name__ == "__main__":
    unittest.main()
