#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS=0

CLI_PROJECT=""
CLI_REGION=""
ARGS=("$@")
for ((i=0; i<${#ARGS[@]}; i++)); do
  case "${ARGS[$i]}" in
    --project-id|--project)
      if (( i + 1 < ${#ARGS[@]} )); then
        CLI_PROJECT="${ARGS[$((i+1))]}"
      fi
      ;;
    --project-id=*|--project=*)
      CLI_PROJECT="${ARGS[$i]#*=}"
      ;;
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

read -r RESOLVED_PROJ RESOLVED_REG < <(
  python3 -c '
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(sys.argv[1], "..")))
import _eval_common as ec
p, _, r = ec.resolve_gcp_context(part_num=3, script_file=sys.argv[1] + "/run-all-evals.py", argv=sys.argv[2:])
print(f"{p or \"unknown\"} {r}")
' "${DIR}" "$@"
) || exit 1

echo "[run-all-evals.sh] Target GCP Project: ${RESOLVED_PROJ:-unknown} (Region: ${RESOLVED_REG:-us-central1})"
python3 "${DIR}/run-all-evals.py" "$@"
EXIT_CODE=$?
echo "[run-all-evals.sh] Finished against project '${RESOLVED_PROJ:-unknown}' (${RESOLVED_REG:-us-central1}) in ${SECONDS}s (exit code: ${EXIT_CODE})"
exit ${EXIT_CODE}
