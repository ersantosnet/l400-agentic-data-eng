#!/usr/bin/env python3
"""
Automated Verification Suite for Step 05 Repo Scaffolding
File: evals/tests/test_scaffold.py
"""

import json
import os
import py_compile
import unittest


class TestRepositoryScaffolding(unittest.TestCase):

    def setUp(self):
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    def test_required_directories_exist(self):
        required_dirs = [
            ".ai-rules",
            "docs/requirements",
            "docs/design",
            "evals",
            "evals/tests",
            "graphify-out",
            "src/pipelines",
            "src/sql",
            "src/dbt/models",
            "src/governance",
            "src/orchestration",
        ]
        for d in required_dirs:
            full_path = os.path.join(self.root_dir, d)
            self.assertTrue(os.path.isdir(full_path), f"Required directory missing: {d}")

    def test_design_documents_exist(self):
        required_designs = [
            "docs/design/DESIGN-01-foundations-and-infra.md",
            "docs/design/DESIGN-02-data-layer.md",
            "docs/design/DESIGN-03-analytics-and-ml.md",
            "docs/design/DESIGN-04-application-layer.md",
            "docs/design/DESIGN-05-verification.md",
        ]
        for doc in required_designs:
            full_path = os.path.join(self.root_dir, doc)
            self.assertTrue(os.path.isfile(full_path), f"Design doc missing: {doc}")

    def test_pipeline_scripts_compile(self):
        scripts = [
            "src/pipelines/01_bronze_ingest.py",
            "src/pipelines/02_silver_transform.py",
            "src/governance/apply_kc_governance.py",
            "src/orchestration/medallion_lakehouse_dag.py",
        ]
        for script in scripts:
            full_path = os.path.join(self.root_dir, script)
            self.assertTrue(os.path.isfile(full_path), f"Script missing: {script}")
            try:
                py_compile.compile(full_path, doraise=True)
            except py_compile.PyCompileError as e:
                self.fail(f"Python syntax compilation failed for {script}: {e}")

    def test_agent_config_validity(self):
        config_path = os.path.join(self.root_dir, "agent-config.json")
        self.assertTrue(os.path.isfile(config_path), "agent-config.json missing")
        with open(config_path, "r") as f:
            config = json.load(f)

        required_keys = [
            "gcp-project-id",
            "primary-region",
            "env",
            "raw-landing-bucket",
            "lakehouse-warehouse-bucket",
            "biglake-bronze-catalog",
            "biglake-silver-catalog",
            "bigquery-lakehouse-dataset",
            "bigquery-gold-dataset",
        ]
        for k in required_keys:
            self.assertIn(k, config, f"Key missing in agent-config.json: {k}")
            self.assertTrue(bool(config[k]), f"Value empty for key: {k}")

    def test_sql_models_and_reconciliation(self):
        gold_sql = os.path.join(self.root_dir, "src/sql/gold_fraud_features.sql")
        self.assertTrue(os.path.isfile(gold_sql), "gold_fraud_features.sql missing")
        with open(gold_sql, "r") as f:
            content = f.read()
        self.assertIn("disputes_by_tx", content, "Pre-aggregation disputes CTE missing in Gold SQL")
        self.assertIn("CLUSTER BY customer_id, loyalty_tier", content, "Clustering clause missing in Gold SQL")

        recon_sql = os.path.join(self.root_dir, "src/sql/reconcile_silver_vs_gold.sql")
        self.assertTrue(os.path.isfile(recon_sql), "reconcile_silver_vs_gold.sql missing")
        with open(recon_sql, "r") as f:
            recon_content = f.read()
        self.assertIn("tx_count_variance", recon_content, "Reconciliation variance checks missing")

    def test_evals_prompts_json(self):
        prompts_path = os.path.join(self.root_dir, "evals/prompts.json")
        self.assertTrue(os.path.isfile(prompts_path), "evals/prompts.json missing")
        with open(prompts_path, "r") as f:
            data = json.load(f)
        self.assertIn("test_suites", data, "test_suites missing in evals/prompts.json")
        self.assertGreaterEqual(len(data["test_suites"]), 4, "Expected at least 4 test suites")

    def test_dq_rules_yaml(self):
        yaml_path = os.path.join(self.root_dir, "src/governance/dq_rules.yaml")
        self.assertTrue(os.path.isfile(yaml_path), "dq_rules.yaml missing")
        with open(yaml_path, "r") as f:
            content = f.read()
        self.assertIn("fraud-gold-dq-scan-dev", content)
        self.assertIn("customer_id", content)
        self.assertIn("masked_ssn", content)

    def test_l400_architectural_code_review(self):
        silver_script = os.path.join(self.root_dir, "src/pipelines/02_silver_transform.py")
        with open(silver_script, "r") as f:
            silver_code = f.read()

        # 1. Check against Gluten fallbacks: Zero Python UDFs
        self.assertNotIn("@udf", silver_code, "Python @udf found! Causes Gluten fallback on Lightning Engine")
        self.assertNotIn("udf(", silver_code, "udf(...) found! Causes Gluten fallback on Lightning Engine")

        # 2. Check DECIMAL(18,2) vs DOUBLE precision traps
        self.assertIn("decimal(18,2)", silver_code, "Financial columns must use decimal(18,2) to prevent precision loss")

        # 3. Check Silver PII leaks: Ensure raw SSN and email are not projected
        self.assertIn(".drop(", silver_code)
        self.assertIn("masked_ssn", silver_code)
        self.assertIn("masked_email", silver_code)

        # 4. Check Dual Iceberg REST catalog specs
        bronze_script = os.path.join(self.root_dir, "src/pipelines/01_bronze_ingest.py")
        with open(bronze_script, "r") as f:
            bronze_code = f.read()
        self.assertIn("vended-credentials", bronze_code)
        self.assertIn("vended-credentials", silver_code)
        self.assertIn("merge-on-read", silver_code)


if __name__ == "__main__":
    unittest.main()
