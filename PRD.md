# Product Requirements Document (PRD) — L400 Agentic Data Engineering

> **Instructions for Customer Engineers (CEs):**
> This `PRD.md` serves as your living architectural specification across **Part 1**, **Part 2**, and **Part 3** of the L400 Agentic Data Engineering workshop. Work with your AI Agent to fill in the `TODO (CE)` sections below as you complete discovery and design checkpoints in each lab.

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

## 🏗️ Part 3: The Build — Agentic Medallion Lakehouse Architecture
<!-- TODO (CE - Part 3): After reviewing the Part 3 lab instructions and profiling the raw landing zone data in GCS, collaborate with your agent to generate the complete Medallion Lakehouse PRD here. -->

### 3.1 Business Context & Target Architecture
- **Business Objective:** `TODO (CE)`
- **Storage & Catalog Topology (Raw GCS -> Bronze Iceberg -> Silver Iceberg -> Gold BigQuery/dbt):** `TODO (CE)`

### 3.2 Raw Data Profile & Silver Data-Hygiene Contract
- **Raw Feeds & Row Counts:** `TODO (CE)`
- **Null Handling, Deduplication & Type Sanitization Rules:** `TODO (CE)`
- **PII Masking & Column Dropping Policy:** `TODO (CE)`

### 3.3 Gold Feature Mart & Cross-Layer Reconciliation
- **Gold Table Grain, Pre-Aggregation CTEs & Clustering:** `TODO (CE)`
- **Silver-to-Gold Financial Invariance Targets:** `TODO (CE)`

### 3.4 Data Mesh Governance, Auto Data Quality & Composer Orchestration
- **Knowledge Catalog Domains, Data Products & Aspects:** `TODO (CE)`
- **Dataplex Auto Data Quality Rules:** `TODO (CE)`
- **Cloud Composer End-to-End DAG Specification:** `TODO (CE)`
