# L400 Agentic Data Engineering — Student Workspace

Welcome to the **L400 Agentic Data Engineering in Google Cloud** hands-on workspace. This repository is structured for **Intent-Driven & Spec-Driven Data Engineering** across all three parts of the workshop:

- **Part 1 — The Troubleshoot:** Diagnose and remediate PySpark execution bottlenecks on Dataproc Lightning Engine (Gluten/Velox).
- **Part 2 — The Build (Qualification & Benchmark):** Qualify a 1,200-job Spark estate for Native Query Engine acceleration, model fleet TCO/ROI, and orchestrate an A/B benchmark in Cloud Composer (Apache Airflow).
- **Part 3 — The Build (Agentic Medallion Lakehouse):** Architect, build, govern, and reconcile an end-to-end Medallion Lakehouse across Cloud Storage, BigLake Metastore (Apache Iceberg), Dataproc Serverless Spark, BigQuery, `dbt-bigquery`, Dataplex Knowledge Catalog, and Cloud Composer.

---

## 📁 Workspace Structure

```text
.
├── AGENTS.md                        # Primary AI Agent Constitution & Router
├── PRD.md                           # Living Product Requirements Document (complete per lab part)
├── .gemini/
│   └── rules/
│       ├── always_create_plan.md    # Enforces structured 6-section execution plans
│       ├── zero_secrets_policy.md   # Enforces strict credential & PII Git hygiene
│       ├── lab_governance.md        # Enforces lab pacing, blind spots, and directory layout
│       ├── spark_standards.md       # Spark, Dataproc & Lightning Engine rules (complete TODOs)
│       ├── lakehouse_standards.md   # BigLake, Iceberg & Governance rules (complete TODOs)
│       ├── bigquery_dbt_standards.md# BigQuery SQL & dbt modeling rules (complete TODOs)
│       └── agent_skills_standards.md# DAK skills, MCP tools & Python environment rules
├── docs/
│   ├── part1/                       # Part 1 reports, physical plans & RCA deliverables
│   ├── part2/                       # Part 2 qualification TSV, ROI JSON & benchmark notes
│   └── part3/                       # Part 3 EDA profiles, schema mappings & design docs
└── src/
    ├── part1/                       # Part 1 remediated PySpark & validation scripts
    ├── part2/                       # Part 2 qualification scripts & Cloud Composer DAGs
    └── part3/                       # Part 3 Medallion pipelines, SQL, dbt, governance & DAGs
```

---

## 🚀 How to Work with Your AI Agent

1. **Follow the Lab Portal Instructions:** Each lab checkpoint on the workshop portal defines the business problem and verification goals.
2. **Practice Context Engineering (`.gemini/rules/` & `PRD.md`):**
   - Inspect the domain rule files inside `.gemini/rules/` (`spark_standards.md`, `lakehouse_standards.md`, `bigquery_dbt_standards.md`) and `PRD.md`.
   - As you discover data anomalies, execution plan fallbacks, and architectural requirements, work with your agent to complete the `<!-- TODO (CE): ... -->` sections so your agent enforces those standards automatically.
3. **Review the 6-Section Execution Plan:**
   - Before writing code or submitting cloud jobs, your agent will ask clarifying questions and present a structured 6-section plan (*Summary*, *What*, *How*, *Files*, *Regression Risk Analysis*, *Clarification Questions*). Review and approve the plan before execution.
