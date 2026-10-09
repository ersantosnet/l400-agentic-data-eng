import os
os.environ["SPARK_CONNECT_MODE_ENABLED"] = "1"

import json
from google.cloud.dataproc_spark_connect import DataprocSparkSession
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    avg,
    broadcast,
    col,
    concat_ws,
    count,
    countDistinct,
    expr,
    length,
    lit,
    lower,
    max as spark_max,
    min as spark_min,
    regexp_extract,
    regexp_replace,
    sha2,
    sum as spark_sum,
    to_timestamp,
    trim,
    upper,
    when,
)

PROJECT_ID = "acme-l400-part3-eri-01"
LOCATION = "us-central1"
SUBNET = "acme-part3-subnet"
SERVICE_ACCOUNT = f"sa-dataproc-serverless@{PROJECT_ID}.iam.gserviceaccount.com"
SESSION_ID = "acme-part3-eda-session"
RAW_BASE = f"gs://{PROJECT_ID}-raw-landing/v0.01"

spark = (
    DataprocSparkSession.builder
    .appName("ACME-Part3-Raw-Feeds-EDA")
    .projectId(PROJECT_ID)
    .location(LOCATION)
    .dataprocSessionId(SESSION_ID)
    .subnetwork(SUBNET)
    .serviceAccount(SERVICE_ACCOUNT)
    .getOrCreate()
)

print(f"Connected to Serverless Spark Session: {SESSION_ID} in {PROJECT_ID} ({LOCATION})")


# Load the 2 domain tables and 3 event streams
df_customers = spark.read.json(f"{RAW_BASE}/customers_crm")
df_merchants = (
    spark.read.option("header", "true")
    .option("inferSchema", "true")
    .option("multiLine", "true")
    .option("escape", "\"")
    .csv(f"{RAW_BASE}/merchants_stores")
)
df_auth = spark.read.json(f"{RAW_BASE}/device_auth_logs")
df_tx = spark.read.json(f"{RAW_BASE}/payment_transactions")
df_disputes = spark.read.json(f"{RAW_BASE}/chargeback_disputes")

datasets = {
    "customers_crm": (df_customers, ["snapshot_date"], "customer_id"),
    "merchants_stores": (df_merchants, ["snapshot_date"], "merchant_id"),
    "device_auth_logs": (df_auth, ["year", "month", "day"], "session_id"),
    "payment_transactions": (df_tx, ["year", "month", "day"], "transaction_id"),
    "chargeback_disputes": (df_disputes, ["year", "month", "day"], "dispute_id"),
}

print("=== SECTION 1: SCHEMAS, PARTITION BREAKDOWN & ROW COUNTS ===")
for name, (df, part_cols, pk_col) in datasets.items():
    print(f"\n--- {name} (PK: {pk_col}) ---")
    df.printSchema()
    part_summary = (
        df.select(*part_cols, col("_metadata.file_path").alias("file_path"), col(pk_col))
        .groupBy(*part_cols)
        .agg(
            count(lit(1)).alias("row_count"),
            countDistinct(col(pk_col)).alias("distinct_pk_count"),
            countDistinct(col("file_path")).alias("file_count"),
        )
        .orderBy(*part_cols)
    )
    part_summary.show(truncate=False)
    totals = df.agg(
        count(lit(1)).alias("total_rows"),
        countDistinct(col(pk_col)).alias("total_distinct_pk"),
    ).collect()[0]
    print(
        f"Total Rows: {totals['total_rows']:,} | Distinct {pk_col}: {totals['total_distinct_pk']:,} "
        f"| Extra Retry/Duplicate Rows: {totals['total_rows'] - totals['total_distinct_pk']:,}"
    )


numeric_cols_map = {
    "customers_crm": (df_customers, ["credit_limit_usd", "reward_points", "home_lat", "home_lon"]),
    "merchants_stores": (df_merchants, ["terminal_monthly_fee_usd", "commission_rate_pct", "store_lat", "store_lon"]),
    "device_auth_logs": (df_auth, ["auth_latency_ms", "risk_score_raw", "login_lat", "login_lon"]),
    "payment_transactions": (df_tx, ["tx_amount", "discount_amount", "lat", "lon"]),
    "chargeback_disputes": (df_disputes, ["dispute_amount", "penalty_fee_usd"]),
}

print("=== SECTION 2: NUMERIC COLUMN PROFILING ===")

for table_name, (df, num_cols) in numeric_cols_map.items():
    print(f"\n--- Numeric Profile: {table_name} ---")
    agg_exprs = [count(lit(1)).alias("total_rows")]
    for c in num_cols:
        s_col = col(c).cast("string")
        # Extract unsigned/signed float after stripping commas (ANSI-safe try_cast)
        num_extracted = expr(f"try_cast(regexp_extract(regexp_replace(cast(`{c}` as string), ',', ''), '(-?[0-9]+(?:\\\\.[0-9]+)?)', 1) as double)")
        is_acct_paren = s_col.rlike(r"\(\s*\$?\s*[0-9]")
        cleaned_val = when(is_acct_paren & (num_extracted > 0), -num_extracted).otherwise(num_extracted)

        agg_exprs.extend([
            count(when(s_col.isNotNull() & (trim(s_col) != ""), 1)).alias(f"{c}__non_null"),
            count(when(s_col.rlike(r"(\$|USD)"), 1)).alias(f"{c}__currency"),
            count(when(s_col.rlike(r","), 1)).alias(f"{c}__comma"),
            count(when(is_acct_paren, 1)).alias(f"{c}__acct_parens"),
            count(when(s_col.rlike(r"(pts|%|ms|deg|\([a-zA-Z]+\))"), 1)).alias(f"{c}__units_or_labels"),
            count(when(s_col.rlike(r"[\*#!~]"), 1)).alias(f"{c}__special_chars"),
            count(when(s_col.rlike(r"[\u00a0\u200b\t]"), 1)).alias(f"{c}__unicode_ws"),
            count(when(s_col.isNotNull() & (trim(s_col) != "") & cleaned_val.isNull(), 1)).alias(f"{c}__unparseable"),
            spark_min(cleaned_val).alias(f"{c}__min"),
            spark_max(cleaned_val).alias(f"{c}__max"),
            avg(cleaned_val).alias(f"{c}__avg"),
        ])

    res = df.agg(*agg_exprs).collect()[0].asDict()
    total_r = res["total_rows"]
    for c in num_cols:
        print(
            f"  Column `{c}` (non-null={res[f'{c}__non_null']:,}/{total_r:,}): "
            f"currency($/USD)={res[f'{c}__currency']:,}, commas={res[f'{c}__comma']:,}, "
            f"acct_parens($x)={res[f'{c}__acct_parens']:,}, units/labels={res[f'{c}__units_or_labels']:,}, "
            f"special(*#!~)={res[f'{c}__special_chars']:,}, unicode_ws={res[f'{c}__unicode_ws']:,}, "
            f"unparseable={res[f'{c}__unparseable']:,} | "
            f"cleaned [min={res[f'{c}__min']}, max={res[f'{c}__max']}, avg={res[f'{c}__avg']:.4f}]"
        )
        samples = [r[0] for r in df.select(col(c).cast("string")).where(col(c).isNotNull()).distinct().limit(4).collect()]
        print(f"    Samples: {samples}")
        if res[f"{c}__acct_parens"] > 0:
            paren_samples = [
                r[0]
                for r in df.select(col(c).cast("string"))
                .where(col(c).cast("string").rlike(r"\(\s*\$?\s*[0-9]"))
                .distinct()
                .limit(4)
                .collect()
            ]
            print(f"    Accounting Paren Samples: {paren_samples}")


print("=== SECTION 3A: 4-CLASS NULL TAXONOMY INVESTIGATION ===")

# Taxonomy specifications for all 5 tables
taxonomy_specs = {
    "customers_crm": {
        "df": df_customers,
        "part_cols": ["snapshot_date"],
        "pk": "customer_id",
        "fk_cols": [],
        "ts_cols": ["signup_timestamp"],
        "metric_cols": ["credit_limit_usd"],
        "opt_cols": ["phone", "loyalty_tier"],
    },
    "merchants_stores": {
        "df": df_merchants,
        "part_cols": ["snapshot_date"],
        "pk": "merchant_id",
        "fk_cols": [],
        "ts_cols": [],
        "metric_cols": ["terminal_monthly_fee_usd", "commission_rate_pct"],
        "opt_cols": ["store_manager_code", "region_notes"],
    },
    "device_auth_logs": {
        "df": df_auth,
        "part_cols": ["year", "month", "day"],
        "pk": "session_id",
        "fk_cols": ["customer_id", "device_id"],
        "ts_cols": ["login_timestamp"],
        "metric_cols": ["auth_latency_ms", "risk_score_raw"],
        "opt_cols": ["user_agent", "mfa_method"],
    },
    "payment_transactions": {
        "df": df_tx,
        "part_cols": ["year", "month", "day"],
        "pk": "transaction_id",
        "fk_cols": ["customer_id", "merchant_id", "session_id", "device_id"],
        "ts_cols": ["tx_timestamp"],
        "metric_cols": ["tx_amount", "discount_amount"],
        "opt_cols": ["promo_code", "device_ip"],
    },
    "chargeback_disputes": {
        "df": df_disputes,
        "part_cols": ["year", "month", "day"],
        "pk": "dispute_id",
        "fk_cols": ["transaction_id", "customer_id", "merchant_id"],
        "ts_cols": ["dispute_timestamp"],
        "metric_cols": ["dispute_amount", "penalty_fee_usd"],
        "opt_cols": ["customer_statement", "agent_notes"],
    },
}

for name, spec in taxonomy_specs.items():
    df = spec["df"]
    part_cols = spec["part_cols"]
    pk = spec["pk"]
    non_part_cols = [c for c in df.columns if c not in part_cols]
    
    # Class N1: Ghost rows where all non-partition attributes are null
    all_null_cond = lit(True)
    for c in non_part_cols:
        all_null_cond = all_null_cond & col(c).isNull()
    n1_ghosts = df.where(all_null_cond).count()
    
    # Class N3a: Critical PK / FK / TS missing or blank
    n3a_pk_cond = col(pk).isNull() | (trim(col(pk).cast("string")) == "")
    n3a_pk_cnt = df.where(n3a_pk_cond).count()
    
    # Class N2: Truncated rows (partial rows with missing PK but some other fields present, or corrupt payloads)
    n2_truncated = n3a_pk_cnt - n1_ghosts
    
    print(f"\n--- 4-Class Null Taxonomy: {name} (Total Rows: {df.count():,}) ---")
    print(f"  [Class N1 - Empty Ghost Rows (all nulls)]: {n1_ghosts:,}")
    print(f"  [Class N2 - Truncated/Corrupt Rows]: {n2_truncated:,}")
    print(f"  [Class N3a - Missing Critical PK (`{pk}`)]: {n3a_pk_cnt:,}")
    
    for fk in spec["fk_cols"]:
        fk_nulls = df.where(col(fk).isNull() | (trim(col(fk).cast("string")) == "")).count()
        print(f"  [Class N3a - Missing Critical FK (`{fk}`)]: {fk_nulls:,}")
        
    for ts in spec["ts_cols"]:
        ts_nulls = df.where(col(ts).isNull() | (trim(col(ts).cast("string")) == "")).count()
        print(f"  [Class N3a - Missing Critical Timestamp (`{ts}`)]: {ts_nulls:,}")
        
    for m in spec["metric_cols"]:
        s_col = col(m).cast("string")
        num_clean = expr(f"try_cast(regexp_extract(regexp_replace(cast(`{m}` as string), ',', ''), '(-?[0-9]+(?:\\\\.[0-9]+)?)', 1) as double)")
        is_acct_paren = s_col.rlike(r"\(\s*\$?\s*[0-9]")
        val = when(is_acct_paren & (num_clean > 0), -num_clean).otherwise(num_clean)
        lte_zero = df.where(val <= 0).count()
        neg_cnt = df.where(val < 0).count()
        zero_cnt = df.where(val == 0).count()
        print(f"  [Class N3b - Metric <= 0 (`{m}`)]: {lte_zero:,} (neg={neg_cnt:,}, zero={zero_cnt:,})")
        
    for opt in spec["opt_cols"]:
        opt_nulls = df.where(col(opt).isNull() | (trim(col(opt).cast("string")) == "")).count()
        pct = (opt_nulls / df.count()) * 100.0
        print(f"  [Class N4 - Benign Null in Optional (`{opt}`)]: {opt_nulls:,} ({pct:.2f}%)")

print("\n=== SECTION 3B: PRIMARY & FOREIGN KEY FORMATTING & REFERENTIAL INTEGRITY ===")
key_specs = {
    "customers_crm": (df_customers, [("customer_id", r"^CUST-[0-9]{7}$")]),
    "merchants_stores": (df_merchants, [("merchant_id", r"^MERCH-[0-9]{5}$")]),
    "device_auth_logs": (
        df_auth,
        [("session_id", r"^SESS-[0-9]{8}$"), ("customer_id", r"^CUST-[0-9]{7}$"), ("device_id", r"^DEV-[A-Z0-9-]+$")],
    ),
    "payment_transactions": (
        df_tx,
        [
            ("transaction_id", r"^TX-[0-9]{8}$"),
            ("session_id", r"^SESS-[0-9]{8}$"),
            ("customer_id", r"^CUST-[0-9]{7}$"),
            ("merchant_id", r"^MERCH-[0-9]{5}$"),
            ("device_id", r"^DEV-[A-Z0-9-]+$"),
        ],
    ),
    "chargeback_disputes": (
        df_disputes,
        [
            ("dispute_id", r"^DISP-[0-9]{6}$"),
            ("transaction_id", r"^TX-[0-9]{8}$"),
            ("customer_id", r"^CUST-[0-9]{7}$"),
            ("merchant_id", r"^MERCH-[0-9]{5}$"),
        ],
    ),
}

for table_name, (df, k_list) in key_specs.items():
    agg_exprs = [count(lit(1)).alias("total_rows")]
    for k_col, pattern in k_list:
        s_col = col(k_col).cast("string")
        cleaned_k = upper(trim(regexp_replace(s_col, r"[\*#!\u00a0\u200b\t ]", "")))
        agg_exprs.extend([
            count(when(s_col != trim(s_col), 1)).alias(f"{k_col}__ws"),
            count(when(s_col.rlike(r"[\*#!\u00a0\u200b]"), 1)).alias(f"{k_col}__noise"),
            count(when(s_col != upper(s_col), 1)).alias(f"{k_col}__lowercase"),
            count(when(~s_col.rlike(pattern), 1)).alias(f"{k_col}__raw_regex_mismatch"),
            count(when(~cleaned_k.rlike(pattern), 1)).alias(f"{k_col}__clean_regex_mismatch"),
        ])
    res = df.agg(*agg_exprs).collect()[0].asDict()
    print(f"\n--- Key Formatting: {table_name} ---")
    for k_col, pattern in k_list:
        print(
            f"  `{k_col}` (pattern {pattern}): ws_padded={res[f'{k_col}__ws']:,}, "
            f"noise(*#!)= {res[f'{k_col}__noise']:,}, lowercase={res[f'{k_col}__lowercase']:,}, "
            f"raw_mismatch={res[f'{k_col}__raw_regex_mismatch']:,}, "
            f"clean_mismatch={res[f'{k_col}__clean_regex_mismatch']:,}"
        )

def clean_key_df(df: DataFrame, col_name: str) -> DataFrame:
    return (
        df.where(col(col_name).isNotNull())
        .select(
            upper(trim(regexp_replace(col(col_name).cast("string"), r"[\*#!\u00a0\u200b\t ]", ""))).alias(col_name)
        )
        .where(col(col_name) != "")
        .distinct()
    )

cust_keys = clean_key_df(df_customers, "customer_id")
merch_keys = clean_key_df(df_merchants, "merchant_id")
sess_keys = clean_key_df(df_auth, "session_id")
tx_keys = clean_key_df(df_tx, "transaction_id")

fk_checks = [
    ("device_auth_logs.customer_id -> customers_crm", clean_key_df(df_auth, "customer_id"), cust_keys, "customer_id"),
    ("payment_transactions.customer_id -> customers_crm", clean_key_df(df_tx, "customer_id"), cust_keys, "customer_id"),
    ("payment_transactions.merchant_id -> merchants_stores", clean_key_df(df_tx, "merchant_id"), merch_keys, "merchant_id"),
    ("payment_transactions.session_id -> device_auth_logs", clean_key_df(df_tx, "session_id"), sess_keys, "session_id"),
    ("chargeback_disputes.transaction_id -> payment_transactions", clean_key_df(df_disputes, "transaction_id"), tx_keys, "transaction_id"),
    ("chargeback_disputes.customer_id -> customers_crm", clean_key_df(df_disputes, "customer_id"), cust_keys, "customer_id"),
    ("chargeback_disputes.merchant_id -> merchants_stores", clean_key_df(df_disputes, "merchant_id"), merch_keys, "merchant_id"),
]

print("\n--- Foreign Key Orphan Check (Distinct Non-Null Cleaned Keys) ---")
for label, child_keys, parent_keys, k_name in fk_checks:
    orphan_cnt = child_keys.join(parent_keys, on=k_name, how="left_anti").count()
    total_child = child_keys.count()
    print(f"  {label}: {orphan_cnt:,} orphan keys out of {total_child:,} distinct child keys")

print("\n=== SECTION 3C: TIMESTAMP FORMAT INSPECTION (ANSI-SAFE) ===")
ts_cols_map = [
    ("customers_crm", df_customers, "signup_timestamp"),
    ("device_auth_logs", df_auth, "login_timestamp"),
    ("payment_transactions", df_tx, "tx_timestamp"),
    ("chargeback_disputes", df_disputes, "dispute_timestamp"),
]
iso_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
slash_regex = r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}"
us_date_regex = r"^\d{2}[-/]\d{2}[-/]\d{4}"

for t_name, df, ts_col in ts_cols_map:
    s_col = trim(col(ts_col).cast("string"))
    parsed_ts = expr(
        f"coalesce("
        f"try_to_timestamp(trim(cast(`{ts_col}` as string))), "
        f"try_to_timestamp(trim(cast(`{ts_col}` as string)), 'yyyy/MM/dd HH:mm:ss'), "
        f"try_to_timestamp(trim(cast(`{ts_col}` as string)), 'MM/dd/yyyy HH:mm:ss'), "
        f"try_to_timestamp(trim(cast(`{ts_col}` as string)), 'dd-MM-yyyy HH:mm:ss')"
        f")"
    )
    stats = df.agg(
        count(lit(1)).alias("total"),
        count(when(col(ts_col).isNull() | (s_col == ""), 1)).alias("null_cnt"),
        count(when(s_col.rlike(iso_regex), 1)).alias("iso_match"),
        count(when(s_col.rlike(slash_regex), 1)).alias("slash_ymd_match"),
        count(when(s_col.rlike(us_date_regex), 1)).alias("us_or_eu_match"),
        count(when(~s_col.rlike(iso_regex) & col(ts_col).isNotNull() & (s_col != ""), 1)).alias("non_iso"),
        count(when(parsed_ts.isNull() & col(ts_col).isNotNull() & (s_col != ""), 1)).alias("unparseable_after_coalesce"),
        spark_min(parsed_ts).alias("min_ts"),
        spark_max(parsed_ts).alias("max_ts"),
    ).collect()[0]
    print(
        f"  {t_name}.{ts_col}: total={stats['total']:,}, nulls={stats['null_cnt']:,}, "
        f"ISO-8601={stats['iso_match']:,}, slash(yyyy/MM/dd)={stats['slash_ymd_match']:,}, "
        f"MM-dd-yyyy/dd-MM-yyyy={stats['us_or_eu_match']:,}, total_non_ISO={stats['non_iso']:,}, "
        f"unparseable_after_coalesce={stats['unparseable_after_coalesce']:,} "
        f"| range=[{stats['min_ts']} .. {stats['max_ts']}]"
    )

print("\n=== SECTION 3D: GATEWAY RETRY DUPLICATE PKS & STATUS BREAKDOWN ===")
for t_name, (df, part_cols, pk_col) in datasets.items():
    data_cols = [c for c in df.columns if c not in part_cols]
    clean_pk = upper(trim(regexp_replace(col(pk_col).cast("string"), r"[\*#!\u00a0\u200b\t ]", "")))
    total_r = df.count()
    non_null_pk_df = df.where(col(pk_col).isNotNull() & (clean_pk != ""))
    non_null_r = non_null_pk_df.count()
    distinct_clean_pk = non_null_pk_df.select(clean_pk.alias("pk")).distinct().count()
    exact_distinct = df.select(*data_cols).distinct().count()
    retry_dups = non_null_r - distinct_clean_pk
    pct = (retry_dups / total_r) * 100.0 if total_r else 0.0
    print(
        f"  {t_name} (`{pk_col}`): total_rows={total_r:,} | non_null_pk_rows={non_null_r:,} "
        f"| distinct_clean_pk={distinct_clean_pk:,} | gateway_retry_dups={retry_dups:,} ({pct:.2f}%) "
        f"| exact_full_row_dups={total_r - exact_distinct:,}"
    )

print("\n--- Payment Transactions Gateway Status Breakdown ---")
df_tx.groupBy(
    upper(trim(regexp_replace(col("gateway_status"), r"[\*#!\u00a0\u200b\t]", ""))).alias("clean_gateway_status"),
    col("gateway_status").alias("raw_gateway_status"),
).count().orderBy(col("count").desc()).show(20, truncate=False)

print("\n=== SECTION 3E: 1-TO-N CHARGEBACK DISPUTES TO PAYMENT TRANSACTIONS CARDINALITY ===")
disp_per_tx = df_disputes.groupBy("transaction_id").agg(count("dispute_id").alias("dispute_count"))
print("Dispute Count Distribution per Transaction ID:")
disp_per_tx.groupBy("dispute_count").count().orderBy("dispute_count").show(20, truncate=False)

print("\n=== SECTION 3F: DEV-FRAUD-999 SHARED DEVICE RING TOPOLOGY ===")
fraud_tx = df_tx.where(col("device_id") == "DEV-FRAUD-999")
print("DEV-FRAUD-999 Activity in payment_transactions:")
print(f"  Total Rows: {fraud_tx.count():,}")
print(f"  Distinct Transactions: {fraud_tx.select('transaction_id').distinct().count():,}")
print(f"  Distinct Compromised Customers: {fraud_tx.select('customer_id').distinct().count():,}")
print(f"  Distinct Payment Cards (card_hash): {fraud_tx.select('card_hash').distinct().count():,}")
print(f"  Distinct Target Merchants: {fraud_tx.select('merchant_id').distinct().count():,}")
print("  Gateway Status Breakdown:")
fraud_tx.groupBy("gateway_status").count().show(truncate=False)

fraud_auth = df_auth.where(col("device_id") == "DEV-FRAUD-999")
print("DEV-FRAUD-999 Activity in device_auth_logs:")
print(f"  Total Rows: {fraud_auth.count():,}")
print(f"  Distinct Customer Accounts: {fraud_auth.select('customer_id').distinct().count():,}")
print(f"  Distinct Sessions: {fraud_auth.select('session_id').distinct().count():,}")


print("=== SECTION 4: PII INVENTORY & GOVERNANCE PROFILING ACROSS ALL 5 TABLES ===")

target_pii_cols = {"ssn", "email", "phone", "billing_address", "device_ip", "full_name", "card_hash", "user_agent", "customer_statement"}

for t_name, (df, part_cols, pk_col) in datasets.items():
    present_pii = [c for c in df.columns if c in target_pii_cols]
    print(f"\n--- PII Columns in `{t_name}`: {present_pii} ---")
    if not present_pii:
        continue
    agg_exprs = [count(lit(1)).alias("total_rows")]
    for c in present_pii:
        s_col = col(c).cast("string")
        agg_exprs.extend([
            count(when(col(c).isNotNull() & (trim(s_col) != ""), 1)).alias(f"{c}__non_null"),
            count(when(s_col.rlike(r"[\*#!\u00a0\u200b\t]"), 1)).alias(f"{c}__dirty_chars"),
            countDistinct(col(c)).alias(f"{c}__distinct"),
        ])
    res = df.agg(*agg_exprs).collect()[0].asDict()
    total_r = res["total_rows"]
    for c in present_pii:
        nn = res[f"{c}__non_null"]
        pct = (nn / total_r) * 100.0 if total_r else 0.0
        print(
            f"  `{c}`: non_null={nn:,}/{total_r:,} ({pct:.2f}%), "
            f"distinct={res[f'{c}__distinct']:,}, dirty_chars(*#!\\t\\u00a0)={res[f'{c}__dirty_chars']:,}"
        )
        samples = [r[0] for r in df.select(col(c).cast("string")).where(col(c).isNotNull()).limit(3).collect()]
        print(f"    Sample raw values: {samples}")

print("\n--- Preview: Silver/Gold Irreversible SHA-256 Pseudonymization (`masked_ssn`, `masked_email`, raw dropped) ---")
print("1. customers_crm Silver Transformation:")
df_customers_silver_preview = (
    df_customers.select(
        upper(trim(col("customer_id"))).alias("customer_id"),
        sha2(regexp_replace(trim(col("ssn")), r"[^0-9]", ""), 256).alias("masked_ssn"),
        sha2(lower(trim(col("email"))), 256).alias("masked_email"),
        when(col("phone").isNotNull(), sha2(regexp_replace(trim(col("phone")), r"[^0-9+]", ""), 256)).alias("masked_phone"),
        sha2(lower(trim(regexp_replace(col("billing_address"), r"[\t\u00a0\u200b]+", " "))), 256).alias("masked_billing_address"),
    )
    .limit(5)
)
df_customers_silver_preview.show(truncate=False)

print("2. payment_transactions Silver Transformation (dropping leaked raw ssn):")
df_tx_silver_preview = (
    df_tx.select(
        upper(trim(col("transaction_id"))).alias("transaction_id"),
        upper(trim(col("customer_id"))).alias("customer_id"),
        sha2(regexp_replace(trim(col("ssn")), r"[^0-9]", ""), 256).alias("masked_ssn"),
        col("card_hash"),
        col("device_id"),
        when(col("device_ip").isNotNull(), sha2(trim(col("device_ip")), 256)).alias("masked_device_ip"),
    )
    .limit(5)
)
df_tx_silver_preview.show(truncate=False)

