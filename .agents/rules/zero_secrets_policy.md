---
description: Mandatory Zero Secrets Policy preventing staging, committing, pushing, or hardcoding credentials, keys, tokens, session state, or PII.
trigger: always_on
---

# Zero Secrets Policy

## 1. Zero Secrets Policy
- **NEVER** stage (`git add`), commit, or push any of the following to Git:
  - Local environment files: `.env`, `.env.*`, `.env.local`, `.env.*.local` (only `.env.example` is permitted).
  - GCP Service Account JSON keys (`*service_account*.json`, `*sa*.json`, `*credentials*.json`).
  - Private cryptographic keys or certificates (`*.key`, `*.pem`, `*.pkcs12`).
  - Real API keys, Bearer tokens, or OAuth secrets (`AIza...`, `ya29...`, etc.).
  - Browser auth sessions, cookies (`*cookies*`, `.notebooklm/`).
  - Local ADK session and database state (`.adk/`, `**/*.sqlite3`, `*.db-journal`).
  - Personal identifiable information (PII) or confidential client datasets.

## 2. Code & Pipeline Enforcement
- Always authenticate to Google Cloud using Application Default Credentials (ADC), Workload Identity, or BigLake credential vending (`vended-credentials`)—never export or reference static service account key files in code.
- Before running any `git add` or `git commit` command, run `git status` and `git diff` to verify that zero files or strings matching the above patterns are included.
