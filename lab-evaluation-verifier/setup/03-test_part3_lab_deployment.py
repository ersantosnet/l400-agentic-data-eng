#!/usr/bin/env python3
"""
Lab Evaluation: L400-agentic-data-eng - setup_part3_lab_deployment
Deep-checks that the Part 3 (Agentic Data Engineering / Medallion Lakehouse) GCP project was
deployed correctly by lab-packs/part3-medallion/deploy.sh (or deploy-all-labs.sh).

Usage: ./03-test_part3_lab_deployment.py --project-id l400-agentic-de-p3-$USER [--region us-central1] [--no-submit|--manual]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _setup_eval_common as c  # noqa: E402

EVAL_NAME = "setup_part3_lab_deployment"
REQUIRED_APIS = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "biglake.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "dataplex.googleapis.com",
    "datacatalog.googleapis.com",
    "bigquerydatapolicy.googleapis.com",
    "datalineage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "compute.googleapis.com",
    "dataproc.googleapis.com",
]
LANDING_FEEDS = [
    "payment_transactions",
    "customers_crm",
    "merchants_stores",
    "device_auth_logs",
    "chargeback_disputes",
]


def build_checks(project: str, region: str) -> list:
    return [
        c.check_apis(project, REQUIRED_APIS),
        c.check_network(project, region, "acme-part3-vpc", "acme-part3-subnet", "allow-spark-internal-part3"),
        c.check_service_account(project),
        c.check_buckets(project, ["raw-landing", "lakehouse-warehouse", "spark-event-logs"]),
        c.check_object_count(project, "Raw landing feeds (v0.01, 5 feeds)", f"gs://{project}-raw-landing/v0.01/", 47, LANDING_FEEDS),
        c.check_bq_datasets(project, ["fraud_detection_db", "fraud_features_gold"]),
        c.check_bq_connection(project, region, "lakehouse-vending-conn"),
        c.check_composer(project, region, "acme-composer-part3"),
    ]


if __name__ == "__main__":
    sys.exit(c.run_setup_eval(3, EVAL_NAME, "Part 3 • Agentic Data Engineering • Lab Deployment Check", build_checks))
