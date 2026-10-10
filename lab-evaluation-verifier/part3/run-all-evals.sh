#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS=0

PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT:-${GOOGLE_CLOUD_PROJECT:-}}}"
if [[ -z "${PROJECT_ID}" ]]; then
  for cfg in "agent-config.json" "../agent-config.json" "../../agent-config.json" "${DIR}/../../agent-config.json"; do
    if [[ -f "${cfg}" ]]; then
      PROJECT_ID="$(python3 -c "import json; print(json.load(open('${cfg}')).get('gcp-project-id', ''))" 2>/dev/null)"
      [[ -n "${PROJECT_ID}" ]] && break
    fi
  done
fi
if [[ -z "${PROJECT_ID}" ]]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"
fi

echo "[run-all-evals.sh] Target GCP Project: ${PROJECT_ID:-unknown}"
python3 "${DIR}/run-all-evals.py" "$@"
EXIT_CODE=$?
echo "[run-all-evals.sh] Finished against project '${PROJECT_ID:-unknown}' in ${SECONDS}s (exit code: ${EXIT_CODE})"
exit ${EXIT_CODE}
