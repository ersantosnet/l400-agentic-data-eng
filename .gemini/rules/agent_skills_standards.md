---
description: Standards for using Data Agent Kit (DAK) skills, MCP tools, Python virtual environments, and authoring modular scripts.
trigger: model_decision
---

# Agent Skills, MCP Tools & Python Scripting Standards

## 1. Skill & MCP Priority (Check Before Coding)
- **Pre-Installed DAK Skills:** Before writing custom automation from scratch, check the pre-installed Google Cloud Data Agent Kit (DAK) skills (`google-cloud-auth-verification`, `discovering-gcp-data-assets`, `gcp-spark`, `data-autocleaning`, `schema-mapping`, `bigquery`, `bigquery-sql`, `dbt-bigquery`, `gcp-managed-airflow-dag-authoring`, `gcp-composer-troubleshooting`, `enforcing-resource-attribution`, `managing-python-dependencies`, `accidental-data-loss-prevention`) and local skills in `.agents/skills/`.
- **MCP Tool Usage:** Prefer structured MCP tools (`dak_bigquery`, `dak_dataproc`, `dak_serverless-spark`, `datacloud_gcs_remote`, `datacloud_knowledge_catalog_remote`) for metadata inspection, job monitoring, and read-only queries.

## 2. Python Dependency & Environment Management
- Follow the `managing-python-dependencies` skill: **NEVER** run global `pip install <pkg>`. Always use a project virtual environment (`.venv`) or `uv`.
- All standalone Python and PySpark scripts must be placed in the corresponding lab folder (`src/part1/`, `src/part2/`, or `src/part3/`).

## 3. Code Quality & Parameterization
- **Dynamic Configuration:** Never hardcode GCP Project IDs, regions, buckets, or credentials. Accept `--project`, `--region`, and `--env` via `argparse` or environment variables.
- **Error Handling & Idempotency:** Wrap cloud API / CLI calls in `try...except` blocks with clear diagnostic logging, and design scripts to be safely re-runnable (idempotent).
