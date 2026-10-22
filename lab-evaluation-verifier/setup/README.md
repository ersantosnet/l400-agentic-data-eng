# Lab Setup Evaluator (`lab-evaluation-verifier/setup/`)

Verifies that the 3 lab GCP projects were deployed correctly by `lab-packs/deploy-all-labs.sh` (or each lab's `deploy.sh`).

```bash
./lab-evaluation-verifier/setup/run-all-evals.sh \
  --p1-project=l400-agentic-de-p1-$USER \
  --p2-project=l400-agentic-de-p2-$USER \
  --p3-project=l400-agentic-de-p3-$USER
```

| Check | Project | Verifies |
| :--- | :--- | :--- |
| `01-test_part1_lab_deployment.py` | Part 1 | APIs, `acme-spark-vpc` / `acme-spark-subnet` / `allow-spark-internal`, `sa-dataproc-serverless`, buckets `-raw-landing`, `-lakehouse-warehouse`, `-spark-event-logs`, seeds `scripts/orders_enrichment.py`, `current_event_log.json`, `orders_raw/` data |
| `02-test_part2_lab_deployment.py` | Part 2 | APIs, `acme-part2-vpc` / `acme-part2-subnet` / `allow-spark-internal-part2`, SA, buckets `-spark-event-logs`, `-lakehouse-warehouse`, `-nqe-audit-results`, 4 pilot event logs, `pure_sql_benchmark.py`, NQE JAR, Composer `acme-composer-part2` (optional) |
| `03-test_part3_lab_deployment.py` | Part 3 | APIs, `acme-part3-vpc` / `acme-part3-subnet` / `allow-spark-internal-part3`, SA, buckets `-raw-landing` (≥ 47 objects across 5 feeds under `v0.01/`), `-lakehouse-warehouse`, `-spark-event-logs`, BigQuery datasets `fraud_detection_db` & `fraud_features_gold`, connection `lakehouse-vending-conn`, Composer `acme-composer-part3` (optional) |

- Each check prints a local **`L400-SETUP-GATE-PASS` / `L400-SETUP-GATE-FAIL`** banner and exits `0` / `1`.
- Composer is opt-in (`deploy.sh --enable-composer`): a missing environment is reported as `SKIP`; an existing environment must be `RUNNING`.
- A signed evidence bundle (`setup_partN_lab_deployment.zip`) is created and submitted to the validator like the part evaluators. Use `--no-submit` to skip submission or `--manual` for manual upload.
- All checks are read-only (`gcloud ... describe/list`, `bq show`).
