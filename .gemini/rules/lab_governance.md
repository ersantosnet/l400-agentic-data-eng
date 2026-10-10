---
description: Mandatory lab governance, anti-cheating blind spots, Clarify-First and Plan-First pacing, and part1/part2/part3 directory layout rules.
trigger: always_on
---

# Educational Lab Governance, Directory Layout & Pacing Rules

You are assisting a Customer Engineer (CE) in a multi-part, hands-on L400 Agentic Data Engineering training lab. You MUST adhere to the following governance rules at all times.

## 1. Anti-Cheating & Evaluator Blind Spot (STRICT)
- The workspace contains automated grading infrastructure (`./lab-evaluation-verifier/`, `proxy.py`, or `*evaluator*` scripts).
- **YOU ARE STRICTLY FORBIDDEN** from reading, listing, grepping, modifying, or executing any files inside `./lab-evaluation-verifier*` or `proxy.py`, or reverse-engineering grading criteria.
- Solve each lab challenge solely through authentic discovery, engineering best practices, and the user's prompts.

## 2. Pacing, Clarify-First & Plan-First Execution
- **Never Jump Ahead:** Only execute the specific lab part and checkpoint requested by the user. Do not pre-build downstream pipelines or future stages unprompted.
- **Check `.gemini/rules/` & `PRD.md` TODOs:** When a task relies on `PRD.md` or a domain rule file (`.gemini/rules/spark_standards.md`, `.gemini/rules/lakehouse_standards.md`, `.gemini/rules/bigquery_dbt_standards.md`) that still has uncompleted `<!-- TODO (CE): ... -->` placeholders for that checkpoint, collaborate with the user to fill in or clarify those engineering rules before generating pipeline code.
- **Always Present a Plan:** Follow `@.gemini/rules/always_create_plan.md` before creating/modifying scripts or submitting cloud jobs.

## 3. Multi-Lab Directory Structure (`part1`, `part2`, `part3`)
To keep the repository organized across all three labs, NEVER dump scripts, SQL files, TSVs, or JSON reports into the project root. Route all deliverables into the corresponding lab part directory:

- **Root Directory (Protected):**
  - Only top-level configuration and documentation files belong in root (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `PRD.md`, `README.md`, `proxy.py`).
- **Part 1 — The Troubleshoot (Spark & Lightning Engine RCA):**
  - Documentation, RCA reports & query plans: `docs/part1/`
  - Remediated PySpark scripts & validation scripts: `src/part1/`
- **Part 2 — The Build (NQE Qualification & Composer Benchmark):**
  - Qualification reports (`AppsRecommendedForBoost.tsv`, `roi_summary.json`, analysis docs): `docs/part2/`
  - Cloud Composer Airflow DAGs & benchmark scripts: `src/part2/`
- **Part 3 — The Build (Medallion Lakehouse Architecture):**
  - EDA profile reports, Schema Mapping Manifesto, & architecture design docs: `docs/part3/`
  - Lakehouse implementation code: `src/part3/` (organized into sub-directories such as `src/part3/pipelines/`, `src/part3/sql/`, `src/part3/dbt/`, `src/part3/governance/`, `src/part3/orchestration/`).
