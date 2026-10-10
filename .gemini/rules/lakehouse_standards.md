---
description: Standards for BigLake Metastore, Apache Iceberg tables, PII masking, and Dataplex Knowledge Catalog governance in Part 3.
trigger: model_decision
---

# BigLake Metastore, Apache Iceberg & Governance Standards

## 1. Platform Mechanics (Pre-Configured)
- **Skill & MCP Usage:** Activate `schema-mapping` before building multi-table transformations, `data-autocleaning` when designing Silver quality rules, and `datacloud_knowledge_catalog_remote` / `discovering-gcp-data-assets` when inspecting catalogs.
- **No Destructive Table Drops:** Never drop or overwrite raw landing buckets. Ask for confirmation before dropping existing Iceberg tables.

---

## 2. Apache Iceberg & BigLake Catalog Configuration (Part 3)
<!-- TODO (CE - Part 3): Complete the Iceberg catalog configuration standards below based on your architecture design and discovery.
Guiding questions to address in your rules:
1. Are we using a single Iceberg catalog or separate catalogs for Bronze and Silver? What Spark Session properties (spark.sql.catalog.<name>...) are required for BigLake Metastore / Iceberg REST catalog with vended credentials?
2. What warehouse paths and namespace conventions should be used for Bronze vs. Silver tables?
3. Which Iceberg format-version and write/merge properties (e.g., copy-on-write vs. merge-on-read) should Silver tables use?
-->
- **Spark Catalog Session Config:** `TODO (CE): Define the required spark.sql.catalog.* properties for Bronze and Silver here.`
- **Table Format & Write Properties:** `TODO (CE): Specify Iceberg format version, partitioning, and write mode standards here.`

---

## 3. PII Protection & Data Governance (Part 3)
<!-- TODO (CE - Part 3): Define the security, PII masking, and Dataplex Knowledge Catalog (KC) governance standards based on the compliance requirements.
Guiding questions to address in your rules:
1. Which columns in the raw datasets contain sensitive PII, how should they be masked in Silver, and what must happen to the raw unmasked PII columns?
2. Which Dataplex Knowledge Catalog aspect types / metadata tags and Auto Data Quality rules must be attached to the tables?
-->
- **PII Masking & Column Dropping Policy:** `TODO (CE): Specify which PII columns must be masked and dropped in Silver here.`
- **Knowledge Catalog & Data Quality Rules:** `TODO (CE): Specify the required Dataplex Knowledge Catalog aspects and DQ assertions here.`
