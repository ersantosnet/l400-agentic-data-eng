# Customer Discovery Document — ACME Inc. Global Payment Fraud Detection Lakehouse

## 0. Document Control & Agentic Context Anchor
| Metadata Field | Value |
| :--- | :--- |
| **Document ID / Filename** | `docs/part3/DISCOVERY.md` (Step 01 of the 8-Step Agentic Data Engineering Lifecycle) |
| **Target GCP Project & Region** | `<TODO: project_id>` • `us-central1` • Initial Environment: `<TODO: dev / qa / prod>` |
| **Customer Stakeholders** | **Devon Patel**, **Marcus Vance**, **Sonia Chen** |
| **Source Artifacts Synthesized** | (Devon Patel's Architectural Brief, 15 Lakehouse Discovery Checkpoints, Pre-Provisioned Environment Inventory) |

## 1. Executive Context & Business Objectives
- **Post-Part 1 & Part 2 Context:** (How legacy Spark batch optimization leads to standardizing greenfield Medallion development)
- **Business Initiative & Fraud Detection Scope:** (Financial pain point, legacy pipeline latency bottleneck, and authorization velocity)
- **Target SDLC Environment & FinOps Attribution Labels:** (Initial build stage, promotion path, and mandatory billing attribution key/value labels)
- **Team Persona Split & Multi-Engine Preferences:** (Core data engineering PySpark engine vs. analytics engineering SQL/dbt engine and downstream AI/BI consumers)

## 2. Stakeholders, Personas & Decision Rights
| Stakeholder | Role / Title | Primary Priorities | Non-Negotiable Acceptance & Sign-Off Criteria |
| :--- | :--- | :--- | :--- |
| **Devon Patel** | Lead Data & Fraud Lakehouse Architect | <TODO> | <TODO> |
| **Marcus Vance** | VP of Enterprise Data & Analytics | <TODO> | <TODO> |
| **Sonia Chen** | Director of Data Platform & Governance | <TODO> | <TODO> |

## 3. Scope, Non-Goals & Measurable Success Metrics
### 3.1 In-Scope (`dev` Build)
- (List the catalog, Bronze, Silver, Gold, reconciliation, governance, data quality, and orchestration deliverables in scope)
### 3.2 Out-of-Scope (Explicit Non-Goals)
- (Explicitly document non-goals such as real-time streaming vs. scheduled batch, direct production execution, etc.)

## 4. Target Environment & Pre-Provisioned GCP Resource Inventory
| Resource Category | Provisioned Identifier | Architectural Role & Binding Flag |
| :--- | :--- | :--- |
| **VPC Network & Subnet (PGA)** | `<TODO>` | `<TODO>` |
| **Execution Service Account** | `<TODO>` | `<TODO>` |
| **Credential Vending Connection** | `<TODO>` | `<TODO>` |
| **Raw Landing & Warehouse Buckets** | `<TODO>` | `<TODO>` |
| **Target BigQuery Datasets** | `<TODO>` | `<TODO>` |

## 5. Source Feeds & Ingestion Semantics
### 5.1 Landing Zone URI & Retention Policy
- (Document raw landing URI root and retention policy across dev vs. prod)
### 5.2 Feed Inventory (Master Snapshots vs. High-Velocity Event Streams)
| Feed Name | Entity Type | File Format | Folder / Partition Layout | Primary & Foreign Keys |
| :--- | :--- | :--- | :--- | :--- |
| `customers_crm` | <TODO> | <TODO> | <TODO> | <TODO> |
| `merchants_stores` | <TODO> | <TODO> | <TODO> | <TODO> |
| `device_auth_logs` | <TODO> | <TODO> | <TODO> | <TODO> |
| `payment_transactions` | <TODO> | <TODO> | <TODO> | <TODO> |
| `chargeback_disputes` | <TODO> | <TODO> | <TODO> | <TODO> |
### 5.3 Partition Date Semantics & Mandatory Audit Columns
- (Clarify whether folder dates represent source business event date vs. ingestion date, and required Bronze metadata columns)

## 6. Medallion Architecture & Storage Security
### 6.1 Catalog Topology & Naming Convention
- (Document how Bronze and Silver catalogs and warehouse prefixes are isolated using `<bu>_<layer>_<env>`)
### 6.2 Storage Access Mode (Zero-Trust Credential Vending Mode)
- (Explain why Credential Vending Mode is selected over direct End-User IAM credentials and which REST headers/connections are required)
### 6.3 Table Format & Write Strategy
- (Specify open table format version and row-level update/delete strategy for Silver upserts and GDPR deletes)
### 6.4 Medallion Tier Responsibilities (Bronze vs. Silver vs. Gold)
- (Define exact schema, retention, and transformation boundaries for each Medallion tier)

## 7. PII Compliance & Data Protection Rules
### 7.1 Bronze Tier PII Controls (1:1 Legal Audit Log + Dynamic Data Masking)
- (How raw cardholder SSNs are retained in Bronze while masked for non-privileged readers via Policy Tags and Data Policies)
### 7.2 Silver & Gold Tier PII Controls (Cryptographic Hashing & Physical Column Removal)
- (Exact normalization and hashing rules for `masked_ssn` and `masked_email`, and requirement to drop cleartext PII columns)

## 8. Data Hygiene, 4-Class Null Contract, Precision Casting & Deduplication
### 8.1 Legacy Mainframe Numeric Formatting & Accounting Parentheses Sanitization
- (Symbols, commas, units, footnote markers, accounting negative parentheses, and required decimal vs. integer vs. floating-point data types)
### 8.2 The 4-Class Null Contract (Corrupt Rows Dropped vs. Benign Nulls Preserved)
| Null Class | Definition & Observed Pattern | Mandatory Silver Action (`DROP` vs. `KEEP`) |
| :--- | :--- | :--- |
| **Class N1** | Empty ghost records | <TODO> |
| **Class N2** | Truncated / malformed payloads | <TODO> |
| **Class N3a / N3b** | Null mandatory keys/timestamps or non-positive mandatory metrics | <TODO> |
| **Class N4** | Benign business nulls in optional columns | <TODO> |
### 8.3 Key Normalization, Categorical Standardization & Multi-Format Timestamp Coalescing
- (Rules for stripping whitespace/casing on PK/FKs, trailing footnote punctuation on categoricals, and parsing multiple timestamp formats)
### 8.4 Gateway Retry Deduplication
- (Window partitioning keys, ordering columns, and status priority tie-breakers per table)

## 9. Fraud Behavioral Signals & Gold Feature Mart (`gold_fraud_features`)
### 9.1 Engineered Behavioral Fraud Signals in Silver (`payment_transactions_silver`)
- (Formulas for net amount after discount, clamped Haversine geospatial distance from home coordinates, and sliding window transaction velocity)
### 9.2 Gold Feature Mart Grain, 1-to-N Dispute Pre-Aggregation & Physical Clustering
- (Target table grain, why chargeback disputes must be pre-aggregated by transaction before joining, physical clustering keys, and handling null loyalty tiers)

## 10. Enterprise Governance, Quality Gates & Orchestration
### 10.1 Knowledge Catalog Data Mesh Structure (Domain & Data Product Mapping)
- (Domain lake, curated zone, certified Data Product, and governance aspect fields attached across all Medallion tables)
### 10.2 Automated SDLC Promotion Gates
- (Automated Data Quality rule dimensions and cross-engine financial reconciliation threshold)
### 10.3 Orchestration & End-to-End Lineage
- (Cloud Composer 3 DAG schedule, task dependency chain, retry policy, and OpenLineage telemetry flags)

## 11. Certified Baseline Metrics & Evaluator Acceptance Criteria
| Medallion Tier / Gate | Target Table(s) | Key Verification Metric | Acceptance Criterion |
| :--- | :--- | :--- | :--- |
| **Phase 1–2 (Catalogs & Bronze)** | 5 `*_bronze` tables | 1:1 raw row retention & audit columns | <TODO: fill after Step 02 EDA> |
| **Phase 3–4 (Silver & PII)** | 5 `*_silver` tables | Clean unique rows, benign nulls, PII drop | <TODO: fill after Step 02 EDA> |
| **Phase 5–6 (Gold & Recon)** | `gold_fraud_features` | Grain, rollups & cross-engine variance | <TODO: fill after Step 02 EDA> |
| **Phase 7 (Governance & DAG)** | Knowledge Catalog & Composer | Policy tags, aspects, DQ scan, lineage | <TODO> |

## 12. Requirements Register & 15-Checkpoint Traceability Matrix
| Checkpoint / Req ID | Discovery Topic | Customer Requirement Summary | Architectural Binding in `SPEC.md` |
| :--- | :--- | :--- | :--- |
| **CP-01 .. CP-15** | <TODO: Map all 15 Discovery Checkpoints> | <TODO> | <TODO> |

## 13. Architecture Decision Log (ADR)
| ADR ID | Decision Title | Chosen Pattern | Rejected Alternative & Rationale |
| :--- | :--- | :--- | :--- |
| **ADR-01 .. ADR-10** | <TODO: Catalog split, Credential Vending, Iceberg V2 MoR, NQE, Decimal math, PII drop, Pre-agg CTE, etc.> | <TODO> | <TODO> |

## 14. Open Questions, Source Discrepancies & Working Assumptions
- (Record any ambiguities between stakeholder memos and physical schemas to verify empirically during Step 02 EDA)

## 15. Architectural Anti-Patterns & Agent Guardrails (Do / Don't)
- **DO NOT:** (e.g., never use Python `@udf`, never use `dropna(how='any')`, never join `chargeback_disputes` 1-to-N directly without pre-aggregating, never cast currency to `DOUBLE`, never retain cleartext `ssn`/`email` in Silver/Gold)
- **DO:** (e.g., use native Spark SQL / Velox expressions, preserve Class N4 benign nulls, use `DECIMAL(18, 2)` for currency, enforce Credential Vending)

## 16. Hand-Off Checklist & Testable Hypotheses for Step 02 (`EDA.md`)
- [ ] **H-01 .. H-10:** (List testable hypotheses on raw row counts, dirty numeric patterns, null classes, timestamp formats, duplicate retry windows, 1-to-N dispute fan-out, and shared device rings to verify in Step 02)
