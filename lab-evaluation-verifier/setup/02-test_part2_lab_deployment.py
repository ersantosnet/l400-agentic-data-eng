#!/usr/bin/env python3
"""
Lab Evaluation: L400-agentic-data-eng - setup_part2_lab_deployment
Deep-checks that the Part 2 (Workload Qualification & Fleet ROI) GCP project was deployed
correctly by lab-packs/part2-qualification/deploy.sh (or deploy-all-labs.sh).

Usage: ./02-test_part2_lab_deployment.py --project-id l400-agentic-de-p2-$USER [--region us-central1] [--no-submit|--manual]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _setup_eval_common as c  # noqa: E402

EVAL_NAME = "setup_part2_lab_deployment"
REQUIRED_APIS = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "compute.googleapis.com",
    "dataproc.googleapis.com",
]
PILOT_EVENT_LOGS = [
    "app-01-pure-sql.json",
    "app-02-decelerated-udf.json",
    "app-03-unsupported-types.json",
    "app-04-rdd-heavy.json",
]


def build_checks(project: str, region: str) -> list:
    seed_objects = [f"gs://{project}-spark-event-logs/{name}" for name in PILOT_EVENT_LOGS]
    seed_objects += [
        f"gs://{project}-lakehouse-warehouse/scripts/pure_sql_benchmark.py",
        f"gs://{project}-lakehouse-warehouse/jars/qualification-tool-assembly.jar",
    ]
    return [
        c.check_apis(project, REQUIRED_APIS),
        c.check_network(project, region, "acme-part2-vpc", "acme-part2-subnet", "allow-spark-internal-part2"),
        c.check_service_account(project),
        c.check_buckets(project, ["spark-event-logs", "lakehouse-warehouse", "nqe-audit-results"]),
        c.check_objects(project, "Pilot event logs, benchmark script & NQE JAR", seed_objects),
        c.check_composer(project, region, "acme-composer-part2"),
    ]


if __name__ == "__main__":
    sys.exit(c.run_setup_eval(2, EVAL_NAME, "Part 2 • Workload Qualification & Fleet ROI • Lab Deployment Check", build_checks))
