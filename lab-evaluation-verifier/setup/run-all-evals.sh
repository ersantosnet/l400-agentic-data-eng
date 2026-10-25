#!/bin/bash
# Lab Setup evaluator: verifies the 3 lab GCP projects deployed by lab-packs/deploy-all-labs.sh.
# Usage: ./lab-evaluation-verifier/setup/run-all-evals.sh --p1-project=<p1> --p2-project=<p2> --p3-project=<p3> [--region=<region>]
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS=0

CLI_REGION=""
ARGS=("$@")
for ((i=0; i<${#ARGS[@]}; i++)); do
  case "${ARGS[$i]}" in
    --region)
      if (( i + 1 < ${#ARGS[@]} )); then
        CLI_REGION="${ARGS[$((i+1))]}"
      fi
      ;;
    --region=*)
      CLI_REGION="${ARGS[$i]#*=}"
      ;;
  esac
done

if [[ -n "${CLI_REGION}" ]] && [[ ! "${CLI_REGION}" =~ ^[a-z]+-[a-z]+[0-9]{1,2}$ ]]; then
  echo "Error: Invalid GCP region '${CLI_REGION}'. Expected format like 'us-central1' or 'europe-west1'." >&2
  exit 1
fi

echo "[run-all-evals.sh] L400 Lab Setup deployment checks (Part 1, Part 2, Part 3)"
python3 "${DIR}/run-all-evals.py" "$@"
EXIT_CODE=$?
echo "[run-all-evals.sh] Finished in ${SECONDS}s (exit code: ${EXIT_CODE})"
exit ${EXIT_CODE}
