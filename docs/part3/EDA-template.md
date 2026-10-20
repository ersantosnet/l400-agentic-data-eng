# Exploratory Data Analysis (EDA) Summary — ACME Inc. Global Payment Fraud Lakehouse

## 0. Document Control & Profiling Scope
| Field | Value |
| :--- | :--- |
| **Document ID / Filename** | `docs/part3/EDA.md` (Step 02 of the 8-Step Agentic Data Engineering Lifecycle) |
| **Upstream Context** | `docs/part3/DISCOVERY.md` |
| **Raw Landing Root URI** | `gs://<TODO: project_id>-raw-landing/v0.01/` |
| **Physical Volume & Row Summary** | `<TODO: file count, total size, total raw rows, clean unique target rows>` |

## 1. Dataset Inventory, Physical Topology & Multi-Day Surge Profile
### 1.1 Feed-by-Feed Summary Table
| Feed Name | Entity Type | Format & Reader Options | Partition / Folder Layout | Files | Raw Rows | Corrupt Rows (`N1`–`N3b`) | Retry Dups | Clean Unique Rows | Primary & Foreign Keys |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `customers_crm` | Master Snapshot | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `merchants_stores` | Master Snapshot | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `device_auth_logs` | Event Stream | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `payment_transactions` | Event Stream | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `chargeback_disputes` | Event Stream | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
### 1.2 Multi-Day Event Stream Surge Wave Profile
| Event Stream | Day 1 Raw / Clean | Day 2 Raw / Clean | Day 3 Raw / Clean | Total Raw / Clean | Daily Share (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `device_auth_logs` | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `payment_transactions` | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
| `chargeback_disputes` | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |

## 2. Complete Column Schema, Data Type & Timestamp Profile
### 2.1 Raw-to-Bronze-to-Silver Column Dictionary (All 5 Feeds)
| Feed Name | Raw Column Name | Observed Raw Sample Values | Null Class / Role | Bronze Type | Silver Target Column & Type | Silver Cleansing / Normalization Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `customers_crm` | <TODO: list all columns> | <TODO> | <TODO> | `STRING` | <TODO> | <TODO> |
| `merchants_stores` | <TODO: list all columns> | <TODO> | <TODO> | `STRING` | <TODO> | <TODO> |
| `device_auth_logs` | <TODO: list all columns> | <TODO> | <TODO> | `STRING` | <TODO> | <TODO> |
| `payment_transactions` | <TODO: list all columns> | <TODO> | <TODO> | `STRING` | <TODO> | <TODO> |
| `chargeback_disputes` | <TODO: list all columns> | <TODO> | <TODO> | `STRING` | <TODO> | <TODO> |
### 2.2 Multi-Format Timestamp Distribution & Cross-Table Causal Ordering
- (Document each timestamp format pattern observed, its percentage share across feeds, and required multi-format parsing order)

## 3. Data Hygiene Anomalies & Categorical Punctuation Defects
### 3.1 Dirty Numeric & Currency Strings
- (Quantify rows containing currency symbols `$`, thousand-commas, unit suffixes `USD`/`ms`/`pts`/`%`/`deg`, footnote markers `*`/`#`/`!`, Unicode spaces, and accounting negative parentheses `($x)`)
### 3.2 CSV Multi-Line Fields & Quoting Behavior (`merchants_stores`)
- (Document embedded newline/carriage-return behavior in `region_notes` and required Spark CSV reader options)
### 3.3 Primary & Foreign-Key Whitespace & Casing Drift
- (Document leading/trailing spaces, tabs, and lowercase drift on `customer_id`, `merchant_id`, `session_id`, `transaction_id`, `dispute_id`, `device_id`)
### 3.4 Categorical & String Punctuation Noise
- (Document trailing footnote punctuation `*`/`!`/`#` on `auth_event`, `loyalty_tier`, `merchant_category`, `reason_code`, dirty `payment_method` codes, and outer whitespace on `full_name`/`store_name`)

## 4. 4-Class Null Taxonomy & Corrupt Record Breakdown
### 4.1 Corrupt Rows to Drop (`Classes N1–N3b`)
| Feed Name | Class N1 (Empty `{}`) | Class N2 (Truncated) | Class N3a (Null PK/FK/TS) | Class N3b (`<= 0` Mandatory Metric) | Total Corrupt Rows Dropped |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customers_crm` .. `chargeback_disputes` | <TODO> | <TODO> | <TODO> | <TODO> | <TODO> |
### 4.2 Class N4 Benign Business Nulls to Preserve
| Feed Name | Optional Nullable Columns | Clean Rows with Benign Nulls (`MUST KEEP`) | Default / Coalesce Rule (Silver vs. Gold) |
| :--- | :--- | :--- | :--- |
| `customers_crm` .. `chargeback_disputes` | <TODO> | <TODO> | <TODO> |

## 5. Gateway Retry Duplicates & Tie-Breaker Analysis
| Feed Name | Partition Key (`PK`) | Duplicate Rows Observed | Status / Timestamp Tie-Breaker Rule | Surviving Clean Unique Rows |
| :--- | :--- | :--- | :--- | :--- |
| `customers_crm` .. `chargeback_disputes` | <TODO> | <TODO> | <TODO> | <TODO> |

## 6. Cross-Table Referential Integrity & 1-to-N Join Cardinalities
### 6.1 Referential Closure Across All PK -> FK Edges (Before vs. After `UPPER(TRIM())`)
- (Document orphan rates before key normalization vs. after `UPPER(TRIM())` across all cross-table foreign keys)
### 6.2 1-to-N `chargeback_disputes` Cardinality Histogram (Why Direct Join Fails)
- (Quantify transactions with multiple disputes and prove why a direct join inflates transaction counts and dollar sums unless pre-aggregated by `transaction_id`)

## 7. Seeded Fraud Behavioral Timelines & Skew Profile
- **Shared-Device Ring Pattern:** (Document anomalous device IDs shared across distinct customer accounts)
- **Cross-Midnight Velocity Bursts & High-Risk MCC Concentration:** (Document rolling 1-hour burst patterns across day boundaries and high-risk merchant categories)

## 8. PII Exposure Audit & Cross-Table Hash Parity
### 8.1 PII Column Inventory Across the 5 Feeds
- (List every direct and indirect PII column per feed and its required Bronze vs. Silver/Gold treatment)
### 8.2 Deterministic SHA-256 Normalization & Cross-Table Parity Check
- (Verify that `sha2(trim(ssn), 256)` and `sha2(lower(trim(email)), 256)` produce 100% matching 64-char hex digests across `customers_crm` and `payment_transactions`)

## 9. Financial Baselines, Dimensional Rollups & Diagnostic Error Signatures
### 9.1 Silver Financial Baselines & Common Bug Signatures
- (Record clean primary/secondary metric sums per table and how common bugs like dropping Class N4 nulls or ignoring accounting parentheses alter the sums)
### 9.2 Ground-Truth Dimensional Rollups (By Payment Method & Loyalty Tier)
- (Record clean transaction counts and gross/net/disputed totals by `payment_method` and `loyalty_tier` for Step 07 reconciliation)

## 10. `DISCOVERY.md` Hypothesis Sign-Off & Step 03 (`SPEC.md`) Hand-Off
| Hypothesis ID | Hypothesis Statement | Empirical Profiling Finding | Status (`CONFIRMED` / `REFINED`) | Exact Rule for `SPEC.md` |
| :--- | :--- | :--- | :--- | :--- |
| **H-01 .. H-10** | <TODO> | <TODO> | <TODO> | <TODO> |
