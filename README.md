# L400 Agentic Data Engineering — Student Workspace

Welcome to the **L400 Agentic Data Engineering in Google Cloud** hands-on workspace. This repository is structured for **Intent-Driven & Spec-Driven Data Engineering** across all three parts of the workshop:

- **Part 1 — The Troubleshoot:** Diagnose and remediate PySpark execution bottlenecks on Dataproc Lightning Engine (Gluten/Velox).
- **Part 2 — The Build (Qualification & Benchmark):** Qualify a 1,200-job Spark estate for Native Query Engine acceleration, model fleet TCO/ROI, and orchestrate an A/B benchmark in Cloud Composer (Apache Airflow).
- **Part 3 — The Build (Agentic Medallion Lakehouse):** Architect, build, govern, and reconcile an end-to-end Medallion Lakehouse across Cloud Storage, BigLake Metastore (Apache Iceberg), Dataproc Serverless Spark, BigQuery, `dbt-bigquery`, Dataplex Knowledge Catalog, and Cloud Composer.

---

## 📁 Workspace Structure

```text
.
├── AGENTS.md                            # Primary AI Agent Constitution & Router
├── PRD.md                               # Living Product Requirements Document (complete per lab part)
├── .env.example                         # Example local environment variables template
├── .gemini/
│   ├── agents/
│   │   └── l400-code-reviewer.md        # Custom read-only subagent for L400 architectural code reviews
│   └── rules/
│       ├── always_create_plan.md        # Enforces structured 6-section execution plans
│       ├── zero_secrets_policy.md       # Enforces strict credential & PII Git hygiene
│       ├── lab_governance.md            # Enforces lab pacing, blind spots, and directory layout
│       ├── spark_standards.md           # Spark, Dataproc & Lightning Engine rules (complete TODOs)
│       ├── lakehouse_standards.md       # BigLake, Iceberg & Governance rules (complete TODOs)
│       ├── bigquery_dbt_standards.md    # BigQuery SQL & dbt modeling rules (complete TODOs)
│       └── agent_skills_standards.md    # DAK skills, MCP tools & Python environment rules
├── docs/
│   ├── part1/                           # Part 1 reports, physical plans & RCA deliverables
│   ├── part2/                           # Part 2 qualification TSV, ROI JSON & benchmark notes
│   └── part3/                           # Part 3 EDA profiles, schema mappings & design docs
└── src/
    ├── part1/                           # Part 1 remediated PySpark & validation scripts
    ├── part2/                           # Part 2 qualification scripts & Cloud Composer DAGs
    └── part3/                           # Part 3 Medallion pipelines, SQL, dbt, governance & DAGs
```

---

## 🚀 How to Work with Your AI Agent

1. **Follow the Lab Portal Instructions:** Each lab checkpoint on the workshop portal defines the business problem and verification goals.
2. **Practice Context Engineering (`.gemini/rules/` & `PRD.md`):**
   - Inspect the domain rule files inside `.gemini/rules/` (`spark_standards.md`, `lakehouse_standards.md`, `bigquery_dbt_standards.md`) and `PRD.md`.
   - As you discover data anomalies, execution plan fallbacks, and architectural requirements, work with your agent to complete the `<!-- TODO (CE): ... -->` sections so your agent enforces those standards automatically.
3. **Delegate Code Reviews to Your Custom Subagent (`.gemini/agents/l400-code-reviewer.md`):**
   - This workspace includes a specialized, read-only custom subagent at `.gemini/agents/l400-code-reviewer.md`.
   - Complete the `<!-- TODO (CE): ... -->` checklist inside `.gemini/agents/l400-code-reviewer.md`, and ask your main agent to invoke the `l400-code-reviewer` subagent (especially during **Part 3 Stage 06: L400 Code Review**) to audit your PySpark, SQL, dbt, and Airflow code in an isolated context window!
4. **Review the 6-Section Execution Plan:**
   - Before writing code or submitting cloud jobs, your agent will ask clarifying questions and present a structured 6-section plan (*Summary of the Plan*, *What You Want to Do*, *How You Want to Do It*, *Files Expected to Change or Create*, *Regression Risk Analysis*, *Clarification Questions*). Review and approve the plan before execution.

---

## ⚡ Pro Tips: Native Antigravity & Jetski Superpowers

Take advantage of these built-in Antigravity & Jetski capabilities during the workshop:
- **`/grill-me` (Interactive Design Interview):** Type `/grill-me` when designing your `PRD.md` or `.gemini/rules/` standards to have the agent interview you and uncover edge cases before writing code.
- **`/compact` (Context Window Reset Between Labs):** Run `/compact` when transitioning from **Part 1 $\rightarrow$ Part 2** or **Part 2 $\rightarrow$ Part 3** to summarize and compact your conversation history so previous logs don't consume your context window.
- **`/learn` (Persist New Rules Automatically):** Whenever you correct the agent or discover a crucial platform behavior, type `/learn` so the agent codifies that lesson into your workspace rules or skills.
- **Interactive Visualizations (`generative_ui`):** Ask your agent to use the `generative_ui` skill to render visual Spark physical plan comparisons, Medallion lineage diagrams, or financial reconciliation dashboards directly inside the chat pane.
