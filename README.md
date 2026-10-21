# L400 Agentic Data Engineering — Student Workspace

Welcome to the **L400 Agentic Data Engineering in Google Cloud** hands-on workspace. This repository is structured for **Intent-Driven & Spec-Driven Data Engineering** across all three parts of the workshop:

- **Part 1 — The Troubleshoot:** Diagnose and remediate PySpark execution bottlenecks on Dataproc Serverless Runtime `2.3` Lightning Engine (Gluten/Velox).
- **Part 2 — The Build (Qualification & Benchmark):** Qualify a 1,200-job Spark estate for Native Query Engine acceleration, model fleet TCO/ROI, and orchestrate an A/B benchmark in Cloud Composer 3 (Apache Airflow).
- **Part 3 — The Build (Agentic Medallion Lakehouse):** Architect, build, govern, and reconcile an end-to-end Medallion Lakehouse across Cloud Storage, Google Lakehouse (Apache Iceberg V2), Dataproc Serverless Spark (`2.3` + NQE), BigQuery, `dbt-bigquery`, Dataplex Knowledge Catalog, and Cloud Composer 3.

---

## 📁 Workspace Structure

```text
.
├── AGENTS.md                            # Primary AI Agent Constitution & Router (symlinked by GEMINI.md & CLAUDE.md)
├── PRD.md                               # Living Product Requirements Document (Parts 1 & 2; links to docs/part3/)
├── .env.example                         # Example local environment variables template
├── .agents/
│   ├── agents/
│   │   └── l400-code-reviewer.md        # Custom read-only subagent for L400 architectural code reviews
│   ├── hooks/
│   │   └── guardrails.py                # Deterministic PreToolUse guardrail script
│   ├── hooks.json                       # Lifecycle hook configuration
│   ├── rules/
│   │   ├── always_create_plan.md        # Enforces structured 6-section execution plans
│   │   ├── zero_secrets_policy.md       # Enforces strict credential & PII Git hygiene
│   │   ├── lab_governance.md            # Enforces lab pacing, blind spots, and directory layout
│   │   ├── spark_standards.md           # Spark, Dataproc & Lightning Engine rules (complete TODOs)
│   │   ├── lakehouse_standards.md       # Google Lakehouse, Iceberg V2 & Governance rules (complete TODOs)
│   │   ├── bigquery_dbt_standards.md    # BigQuery SQL & dbt modeling rules (complete TODOs)
│   │   └── agent_skills_standards.md    # DAK skills, MCP tools & Python environment rules
│   └── skills/
│       └── skill-creator/               # Skill authoring & evaluation toolkit
├── docs/
│   ├── part1/                           # Part 1 reports, physical plans & RCA deliverables
│   ├── part2/                           # Part 2 qualification TSV, ROI JSON & benchmark notes
│   └── part3/                           # Part 3 8-Step Spec-Driven Planning Docs & Un-Spoiled Templates
│       ├── DISCOVERY-template.md        # Step 01 skeleton (§0–§16) -> copy/fill to create DISCOVERY.md
│       ├── EDA-template.md              # Step 02 skeleton (§0–§10) -> copy/fill to create EDA.md
│       └── SPEC-template.md             # Step 03 skeleton (§0–§9)  -> copy/fill to create SPEC.md
└── src/
    ├── part1/                           # Part 1 remediated PySpark & validation scripts
    ├── part2/                           # Part 2 qualification scripts & Cloud Composer DAGs
    └── part3/                           # Part 3 Medallion codebase (matches SPEC.md §0.3)
        ├── scripts/                     # 01_bronze_ingest.py, 02_silver_transform.py,
        │                                # register_bq_external_tables.py, apply_kc_governance.py
        ├── dbt_project/                 # dbt_project.yml, profiles.yml, models/gold_fraud_features.sql
        ├── sql/                         # gold_fraud_features.sql, reconcile_silver_vs_gold.sql
        └── dags/                        # medallion_lakehouse_dag.py (+ src/part3/dq_rules.yaml)
```

---

## 🚀 How to Work with Your AI Agent

1. **Follow the Lab Portal Instructions:** Each lab checkpoint on the workshop portal defines the business problem and verification goals.
2. **Practice Spec-Driven & Context Engineering (`.agents/rules/`, `PRD.md`, & `docs/part3/`):**
   - Inspect the domain rule files inside `.agents/rules/` (`spark_standards.md`, `lakehouse_standards.md`, `bigquery_dbt_standards.md`).
   - In **Part 3**, collaborate with your agent to generate `docs/part3/DISCOVERY.md`, `docs/part3/EDA.md`, and `docs/part3/SPEC.md` directly from the included `*-template.md` skeletons, then validate each document with the **Planning Document Review & AI Coaching** tool on `/part3` before generating pipeline code!
3. **Delegate Code Reviews to Your Custom Subagent (`.agents/agents/l400-code-reviewer.md`):**
   - This workspace includes a specialized, read-only custom subagent at `.agents/agents/l400-code-reviewer.md`.
   - Complete the `<!-- TODO (CE): ... -->` checklist inside `.agents/agents/l400-code-reviewer.md`, and ask your main agent to invoke the `l400-code-reviewer` subagent (especially during **Part 3 Step 05: Review the Code and Assets Generated**) to audit your PySpark, SQL, dbt, and Airflow code in an isolated context window!
4. **Review the 6-Section Execution Plan:**
   - Before writing code or submitting cloud jobs, your agent will ask clarifying questions and present a structured 6-section plan (*Summary of the Plan*, *What You Want to Do*, *How You Want to Do It*, *Files Expected to Change or Create*, *Regression Risk Analysis*, *Clarification Questions*). Review and approve the plan before execution.

---

## ⚡ Pro Tips: Native Antigravity & Jetski Superpowers

Take advantage of these built-in Antigravity & Jetski capabilities during the workshop:
- **`/grill-me` (Interactive Design Interview):** Type `/grill-me` when designing your `DISCOVERY.md`, `SPEC.md`, or `.agents/rules/` standards to have the agent interview you and uncover edge cases before writing code.
- **`/goal` (Autonomous Spec Loop in Step 04):** Once `docs/part3/SPEC.md` passes review, consider using `/goal` in Step 04 so your agent loops autonomously over every deliverable in `SPEC.md` until verified.
- **`/compact` (Context Window Reset Between Labs):** Run `/compact` when transitioning from **Part 1 $\rightarrow$ Part 2** or **Part 2 $\rightarrow$ Part 3** to summarize and compact your conversation history so previous logs don't consume your context window.
- **`/learn` (Persist New Rules Automatically):** Whenever you correct the agent or discover a crucial platform behavior, type `/learn` so the agent codifies that lesson into your workspace rules or skills.
- **Interactive Visualizations (`generative_ui`):** Ask your agent to use the `generative_ui` skill to render visual Spark physical plan comparisons, Medallion lineage diagrams, or financial reconciliation dashboards directly inside the chat pane.
