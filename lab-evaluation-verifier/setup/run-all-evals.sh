#!/bin/bash
# Lab Setup evaluator: verifies the 3 lab GCP projects deployed by lab-packs/deploy-all-labs.sh.
# Usage: ./lab-evaluation-verifier/setup/run-all-evals.sh --p1-project=<p1> --p2-project=<p2> --p3-project=<p3>
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS=0

echo "[run-all-evals.sh] L400 Lab Setup deployment checks (Part 1, Part 2, Part 3)"
python3 "${DIR}/run-all-evals.py" "$@"
EXIT_CODE=$?
echo "[run-all-evals.sh] Finished in ${SECONDS}s (exit code: ${EXIT_CODE})"
exit ${EXIT_CODE}
