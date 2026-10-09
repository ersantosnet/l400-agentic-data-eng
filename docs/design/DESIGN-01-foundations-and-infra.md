# DESIGN-01: Foundations & Infrastructure Architecture

## 1. Business Objective
Establish the foundational Google Cloud Platform infrastructure for the ACME Global Payment Fraud Lakehouse (`dev` environment). This ensures tier-isolated storage, zero-trust credential vending, secure networking, and Lakehouse catalog connectivity without static credentials or excessive privileges.

## 2. Infrastructure Specifications & Bindings

### 2.1 Core GCP Topology
* **GCP Project:** `acme-l400-part3-eri-01` (`--project=acme-l400-part3-eri-01`)
* **Primary Region:** `us-central1`
* **VPC Subnetwork:** `acme-part3-subnet`
* **Dataproc Service Account:** `sa-dataproc-serverless@acme-l400-part3-eri-01.iam.gserviceaccount.com`

### 2.2 Storage & Catalog Isolation
* **Raw Landing Bucket:** `gs://acme-l400-part3-eri-01-raw-landing`
  * Ingestion prefix: `v0.01/`
* **Lakehouse Warehouse Bucket:** `gs://acme-l400-part3-eri-01-lakehouse-warehouse`
  * Bronze warehouse: `bronze_dev/warehouse`
  * Silver warehouse: `silver_dev/warehouse`
  * DAGs location: `dags/`
* **Spark Event Logs Bucket:** `gs://acme-l400-part3-eri-01-spark-event-logs`

### 2.3 BigLake Apache Iceberg REST Catalogs
* **Bronze Catalog:** `acme_bronze_dev` (`bl://projects/acme-l400-part3-eri-01/catalogs/acme_bronze_dev`)
* **Silver Catalog:** `acme_silver_dev` (`bl://projects/acme-l400-part3-eri-01/catalogs/acme_silver_dev`)
* **BigQuery Datasets:**
  * Lakehouse metadata dataset: `fraud_detection_db`
  * Gold curated native dataset: `fraud_features_gold`
* **BigQuery Cloud Resource Connection:**
  * `projects/acme-l400-part3-eri-01/locations/us-central1/connections/lakehouse-vending-conn`
  * Credential Mode: `--credential-mode=vended-credentials`

### 2.4 FinOps & Labeling Governance
All provisioned resources must enforce the following mandatory labels:
```yaml
env: dev
cost_center: fraud_prevention
workload: fraud_lakehouse
```

## 3. Acceptance Criteria
1. Cloud Storage buckets exist, enforce uniform bucket-level access, and are regionally co-located in `us-central1`.
2. Both BigLake REST catalogs (`acme_bronze_dev`, `acme_silver_dev`) are linked to BigQuery connection `lakehouse-vending-conn`.
3. Dataproc Serverless service account possesses necessary BigLake, Dataproc Worker, and BigQuery permissions without direct Storage Admin or static JSON keys.
