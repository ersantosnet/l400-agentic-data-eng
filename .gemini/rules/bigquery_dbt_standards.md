---
description: Standards for BigQuery SQL optimization, BigLake external tables, dbt-bigquery Gold layer modeling, and financial reconciliation in Part 3.
trigger: model_decision
---

# BigQuery SQL & dbt Modeling Standards

## 1. Platform Mechanics (Pre-Configured)
- **Skill & MCP Usage:** Always load the `bigquery`, `bigquery-sql`, and `dbt-bigquery` skills when authoring SQL or dbt models. Use `enforcing-resource-attribution` when executing `bq` or `gcloud` CLI commands.
- **Query Verification:** Use `dak_bigquery` or `datacloud_bigquery_remote` MCP tools to dry-run and verify SQL queries and inspect table metadata.

---

## 2. BigLake External Tables & Gold Feature Mart Modeling (Part 3)
<!-- TODO (CE - Part 3): Define the BigQuery and dbt modeling standards for the Gold layer based on your Silver-to-Gold architecture design.
Guiding questions to address in your rules:
1. How are the Silver Iceberg tables exposed to BigQuery, and where does the Gold feature mart live?
2. What join cardinality trap exists between the core fact table and child tables (e.g., multiple rows per parent key), and how must child tables be pre-aggregated in CTEs to prevent row fan-out and inflated financial sums?
3. What Partitioning (`PARTITION BY`) and Clustering (`CLUSTER BY`) strategy should be applied to the Gold table?
-->
- **Join Cardinality & Pre-Aggregation Rule:** `TODO (CE): Define how 1:N child tables must be pre-aggregated before joining into the Gold mart here.`
- **Partitioning & Clustering Strategy:** `TODO (CE): Define the PARTITION BY and CLUSTER BY columns for the Gold table here.`
- **dbt Project & Testing Conventions:** `TODO (CE): Define dbt materialization, staging/marts folder conventions, and schema.yml test requirements here.`

---

## 3. Cross-Layer Reconciliation & Financial Invariance (Part 3)
<!-- TODO (CE - Part 3): Define the verification queries and invariance assertions required to prove zero data loss or inflation between Silver and Gold.
Guiding questions to address in your rules:
1. Which row counts and financial sum metrics must match exactly (`0.00` variance) between the Silver tables and the Gold mart?
-->
- **Reconciliation Invariance Checks:** `TODO (CE): Specify the mandatory Silver-vs-Gold row count and sum reconciliation checks here.`
