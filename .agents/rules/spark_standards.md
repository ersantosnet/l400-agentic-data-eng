---
description: Standards for PySpark, Dataproc Clusters and Serverless, Lightning Engine (Gluten/Velox), NQE Qualification, and Airflow Spark benchmarking across Parts 1, 2, and 3.
trigger: model_decision
---

# Spark, Dataproc & Lightning Engine Standards

## 1. Platform Mechanics (Pre-Configured)
- **Dynamic Parameterization:** Always accept `--project`, `--region`, `--env`, and bucket/cluster names via CLI arguments (`argparse`) or environment variables. Never hardcode GCP project IDs or bucket URIs.
- **Skill & MCP Usage:** Activate the `gcp-spark` skill and use `dak_dataproc` / `dak_serverless-spark` MCP tools when inspecting clusters, submitting jobs, or analyzing logs.
- **Pre-Flight Compilation:** Always validate PySpark scripts locally using `python3 -m py_compile <script.py>` before uploading to GCS or submitting to Dataproc.

---

## 2. Part 1 Standards: Lightning Engine & Vectorized Execution
<!-- TODO (CE - Part 1): After completing Step 1 & Step 2 of Part 1 (Physical Plan & Event Log Analysis), document your Spark optimization rules below so the agent enforces them when refactoring your pipeline.
Guiding questions to address in your rules:
1. Why did the legacy PySpark job fall back from Native C++ Vectorized execution (Gluten/Velox) to row-by-row execution?
2. What is our strict policy on Python UDFs (@udf / spark.udf.register) vs. native pyspark.sql.functions?
3. How must the execution plan (df.explain(True)) be verified before and after remediation?
-->
- **Vectorization Rule:** `TODO (CE): Define Python UDF vs. Native Spark SQL expressions policy here.`
- **Plan Verification Rule:** `TODO (CE): Define how physical execution plans must be checked for fallback operators here.`

---

## 3. Part 2 Standards: NQE Qualification & Airflow Benchmarking
<!-- TODO (CE - Part 2): Define the filtering criteria and benchmarking standards for evaluating Spark workloads and authoring the Cloud Composer A/B DAG.
Guiding questions to address in your rules:
1. Which columns and thresholds in the Qualification Tool output determine whether an application is recommended for Native Query Engine (Lightning Engine) boost?
2. How should the Cloud Composer (Airflow) DAG structure the parallel A/B comparison between standard Dataproc and Lightning Engine?
-->
- **Qualification Filtering Criteria:** `TODO (CE): Specify the qualification filter thresholds and output schema here.`
- **Benchmark DAG Standards:** `TODO (CE): Specify the Airflow operator conventions, cluster routing, and runtime comparison logic here.`

---

## 4. Part 3 Standards: Medallion PySpark Ingestion & Silver Transformations
<!-- TODO (CE - Part 3): After completing Raw Data Discovery on the landing zone files, define the PySpark ingestion (Bronze) and data-hygiene transformation (Silver) rules below.
Guiding questions to address in your rules:
1. How should Bronze ingestion handle raw schemas, corrupt records, and audit metadata?
2. What specific data quality anomalies discovered in the raw data (e.g., duplicates, status casing, date formats, sentinel values, orphaned keys, monetary precision) must be cleaned in Silver?
-->
- **Bronze Ingestion Rules:** `TODO (CE): Define Bronze raw schema preservation and metadata rules here.`
- **Silver Data Hygiene & Casting Rules:** `TODO (CE): Define Silver deduplication, type casting (e.g., financial precision), and anomaly cleaning rules here.`
