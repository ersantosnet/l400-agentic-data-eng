---
description: Standards for using Data Agent Kit (DAK) skills, MCP tools, custom subagents, Python virtual environments, and authoring modular scripts.
trigger: model_decision
---

# Agent Skills, MCP Tools, Subagents & Python Scripting Standards

## 1. Skill & MCP Priority (Check Before Coding)
- **Pre-Installed DAK Skills:** Before writing custom automation from scratch, check the pre-installed Google Cloud Data Agent Kit (DAK) skills (`google-cloud-auth-verification`, `discovering-gcp-data-assets`, `gcp-spark`, `data-autocleaning`, `schema-mapping`, `bigquery`, `bigquery-sql`, `dbt-bigquery`, `gcp-managed-airflow-dag-authoring`, `gcp-composer-troubleshooting`, `enforcing-resource-attribution`, `managing-python-dependencies`, `accidental-data-loss-prevention`) and local skills in `.agents/skills/`.
- **MCP Tool Usage & Plugin Auth:** Prefer structured MCP tools (`dak_bigquery`, `dak_dataproc`, `dak_serverless-spark`, `datacloud_gcs_remote`, `datacloud_knowledge_catalog_remote`) for metadata inspection, job monitoring, and read-only queries. When verifying authentication or troubleshooting a DAK MCP error, call `list_plugin_accounts` alongside `google-cloud-auth-verification` to confirm the user's connected plugin account status.
- **Subagent Delegation (`l400-code-reviewer`):** When performing architectural code reviews across `src/part1/`, `src/part2/`, or `src/part3/`, delegate to the custom read-only `.gemini/agents/l400-code-reviewer.md` subagent via `invoke_subagent` to keep the primary conversation context clean.

## 2. Python Dependency & Environment Management
- Follow the `managing-python-dependencies` skill: **NEVER** run global `pip install <pkg>`. Always use a project virtual environment (`.venv`) or `uv`.
- All standalone Python and PySpark scripts must be placed in the corresponding lab folder (`src/part1/`, `src/part2/`, or `src/part3/`).

## 3. Code Quality & Parameterization
- **Dynamic Configuration:** Never hardcode GCP Project IDs, regions, buckets, or credentials. Accept `--project`, `--region`, and `--env` via `argparse` or environment variables (see `.env.example`).
- **Error Handling & Idempotency:** Wrap cloud API / CLI calls in `try...except` blocks with clear diagnostic logging, and design scripts to be safely re-runnable (idempotent).
