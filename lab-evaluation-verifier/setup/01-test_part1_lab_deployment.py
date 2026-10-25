#!/usr/bin/env python3
"""
Lab Evaluation: L400-agentic-data-eng - setup_part1_lab_deployment
Deep-checks that the Part 1 (The Troubleshoot) GCP project was deployed correctly
by lab-packs/part1-troubleshoot/deploy.sh (or deploy-all-labs.sh).

Usage: ./01-test_part1_lab_deployment.py --project-id l400-agentic-de-p1-$USER [--region us-central1] [--no-submit|--manual]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _setup_eval_common as c  # noqa: E402

EVAL_NAME = "setup_part1_lab_deployment"
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


def build_checks(project: str, region: str) -> list:
    return [
        c.check_apis(project, REQUIRED_APIS),
        c.check_network(project, region, "acme-spark-vpc", "acme-spark-subnet", "allow-spark-internal"),
        c.check_service_account(project),
        c.check_buckets(project, ["raw-landing", "lakehouse-warehouse", "spark-event-logs"], region),
        c.check_objects(project, "Seed scripts & event logs", [
            f"gs://{project}-lakehouse-warehouse/scripts/orders_enrichment.py",
            f"gs://{project}-spark-event-logs/current_event_log.json",
        ]),
        c.check_object_count(project, "Raw orders landing data", f"gs://{project}-raw-landing/orders_raw/", 1),
    ]


if __name__ == "__main__":
    sys.exit(c.run_setup_eval(1, EVAL_NAME, "Part 1 • The Troubleshoot • Lab Deployment Check", build_checks))
