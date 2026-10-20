# Product Requirements Document (PRD) — L400 Agentic Data Engineering

> **Instructions for Customer Engineers (CEs):**
> Use this `PRD.md` as your living architectural specification for **Part 1** and **Part 2**, and follow the dedicated 3-document Spec-Driven workflow in **`docs/part3/`** (`DISCOVERY.md` $\rightarrow$ `EDA.md` $\rightarrow$ `SPEC.md`) for **Part 3**.

---

## 🌍 Active Lab Environment Coordinates
<!-- TODO (CE): Populate or update your active GCP project and region for the current lab part. -->
- **Active Lab Part:** `TODO (CE): Part 1 / Part 2 / Part 3`
- **GCP Project ID:** `TODO (CE)`
- **Primary Region:** `us-central1`

---

## 🔧 Part 1: The Troubleshoot — Spark & Lightning Engine RCA
<!-- TODO (CE - Part 1): Document the findings from your Spark Event Log & Physical Plan investigation and your target remediation requirements. -->
- **Problem Statement:** `TODO (CE): Describe the performance regression observed on the orders enrichment pipeline.`
- **Root Cause (Physical Plan & Operator Fallback):** `TODO (CE): Document which operator caused Lightning Engine (Gluten/Velox) fallback and why.`
- **Target Deliverables (`src/part1/` & `docs/part1/`):**
  - `TODO (CE): List target script(s), validation parity checks, and RCA report path.`

---

## 📊 Part 2: The Build — NQE Fleet Qualification & Airflow Benchmark
<!-- TODO (CE - Part 2): Document your qualification filtering criteria, fleet ROI projections, and Cloud Composer A/B DAG specification. -->
- **Qualification Scope & Filtering Rules:** `TODO (CE): Define criteria for selecting candidate Spark apps from the 1,200-job estate.`
- **Fleet TCO / ROI Summary:** `TODO (CE): Record qualified app count and projected compute savings.`
- **Airflow Benchmark DAG Specification (`src/part2/` & `docs/part2/`):**
  - `TODO (CE): Define DAG ID, cluster comparison tasks, and output deliverables.`

---

## 🏗️ Part 3: The Build — Agentic Medallion Lakehouse (Managed in `docs/part3/`)

For **Part 3**, follow the **8-Step Agentic Data Engineering Lifecycle** on the workshop portal and author your three specification documents directly inside `docs/part3/` using the included un-spoiled templates:

1. **Step 01 — Customer Discovery (`docs/part3/DISCOVERY.md`):** Initialize from [`docs/part3/DISCOVERY-template.md`](docs/part3/DISCOVERY-template.md) (`§0–§16`) to synthesize Devon Patel's brief and all 15 Lakehouse Discovery Checkpoints.
2. **Step 02 — Exploratory Data Analysis (`docs/part3/EDA.md`):** Initialize from [`docs/part3/EDA-template.md`](docs/part3/EDA-template.md) (`§0–§10`) to record empirical data profiling across all 5 raw feeds in `gs://${PROJECT_ID}-raw-landing/v0.01/`.
3. **Step 03 — Master Technical Specification (`docs/part3/SPEC.md`):** Initialize from [`docs/part3/SPEC-template.md`](docs/part3/SPEC-template.md) (`§0–§9`) to define the complete Schema Mapping Manifesto and target codebase contract under `src/part3/{scripts,dbt_project,sql,dags}/`.
   - *Tip:* Upload or paste each document into the **Planning Document Review & AI Coaching** panel on `/part3` before starting Step 04 code generation!
