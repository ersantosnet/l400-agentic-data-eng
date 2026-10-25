#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# ACME Inc. Retail Modernization — L400 Workshop Master Provisioner
# Deploys Part 1, Part 2, and Part 3 GCP Lab Environments Sequentially
# Script: lab-packs/deploy-all-labs.sh
# ==============================================================================

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.jetski"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

# Colors for terminal styling
BOLD=$'\033[1m'
GREEN=$'\033[0;32m'
CYAN=$'\033[0;36m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
NC=$'\033[0m' # No Color

P1_PROJECT=""
P2_PROJECT=""
P3_PROJECT=""
BILLING_ACCOUNT=""
REGION="${GCP_REGION:-${REGION:-us-central1}}"
TESTER_EMAIL=""
SEED_MODE="fast"
USE_GCLOUD=false
SKIP_CONFIRM=false

validate_region() {
  local reg="${1:-}"
  if [[ ! "${reg}" =~ ^[a-z]+-[a-z]+[0-9]{1,2}$ ]]; then
    echo -e "${RED}[ERROR] Invalid GCP region '${reg}'. Expected format like 'us-central1', 'us-east4', or 'europe-west1'.${NC}"
    exit 1
  fi
}

usage() {
  cat <<EOF
${BOLD}ACME Inc. L400 Workshop — Master 3-Lab Turnkey Provisioner${NC}

${BOLD}USAGE:${NC}
  ./deploy-all-labs.sh [OPTIONS]

${BOLD}OPTIONS:${NC}
  --p1-project=PROJECT_ID       Target GCP Project ID for Part 1 (Default: l400-agentic-de-p1-<ldap>)
  --p2-project=PROJECT_ID       Target GCP Project ID for Part 2 (Default: l400-agentic-de-p2-<ldap>)
  --p3-project=PROJECT_ID       Target GCP Project ID for Part 3 (Default: l400-agentic-de-p3-<ldap>)
  --billing-account=ID          Billing Account ID (Auto-detected once if omitted)
  --region=REGION               Compute and storage region (Default: us-central1)
  --tester-email=EMAIL          Student/CE email for IAM bindings (Default: active gcloud user)
  --seed-mode=fast|generate     Dataset seeding mode across labs (Default: fast)
  --use-gcloud                  Use native gcloud/bq CLI fallback instead of Terraform
  -y, --yes                     Skip upfront confirmation prompt
  -h, --help                    Display this help message

${BOLD}EXAMPLES:${NC}
  # Recommended: Deploy all 3 labs with explicit project IDs from the Lab Setup page
  ./deploy-all-labs.sh \\
    --p1-project=l400-agentic-de-p1-erisantos \\
    --p2-project=l400-agentic-de-p2-erisantos \\
    --p3-project=l400-agentic-de-p3-erisantos

  # Zero-argument mode (auto-derives project IDs from active gcloud user LDAP)
  ./deploy-all-labs.sh
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --p1-project=*)
      P1_PROJECT="${1#*=}"
      shift
      ;;
    --p2-project=*)
      P2_PROJECT="${1#*=}"
      shift
      ;;
    --p3-project=*)
      P3_PROJECT="${1#*=}"
      shift
      ;;
    --billing-account=*)
      BILLING_ACCOUNT="${1#*=}"
      shift
      ;;
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --tester-email=*)
      TESTER_EMAIL="${1#*=}"
      shift
      ;;
    --seed-mode=*|--data-mode=*)
      SEED_MODE="${1#*=}"
      shift
      ;;
    --use-gcloud)
      USE_GCLOUD=true
      shift
      ;;
    -y|--yes)
      SKIP_CONFIRM=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo -e "${RED}[ERROR] Unknown option: $1${NC}"
      usage
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

REGION="$(echo "${REGION}" | tr '[:upper:]' '[:lower:]')"
validate_region "${REGION}"

echo -e "\n${BOLD}${CYAN}================================================================================${NC}"
echo -e "${BOLD}${CYAN}       ACME INC. — L400 MASTER LAB PROVISIONER (PARTS 1, 2 & 3 SEQUENTIAL)      ${NC}"
echo -e "${BOLD}${CYAN}================================================================================${NC}\n"

# ------------------------------------------------------------------------------
# 1. Pre-Flight Authentication & Identity Resolution
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Pre-Flight] Validating Local Tooling, Identity & Billing Account...${NC}"
if ! command -v gcloud &>/dev/null; then
  echo -e "${RED}[ERROR] 'gcloud' CLI is not installed. Please install the Google Cloud SDK.${NC}"
  exit 1
fi

ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  echo -e "${RED}[ERROR] No active gcloud authenticated account found. Run 'gcloud auth login'.${NC}"
  exit 1
fi

if [[ -z "${TESTER_EMAIL}" ]]; then
  TESTER_EMAIL="${ACTIVE_ACCOUNT}"
fi

USER_LDAP="${ACTIVE_ACCOUNT%%@*}"
USER_LDAP="$(echo "${USER_LDAP}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9-]+/-/g; s/^-+|-+$//g')"
[[ -z "${USER_LDAP}" ]] && USER_LDAP="ce-user"

[[ -z "${P1_PROJECT}" ]] && P1_PROJECT="l400-agentic-de-p1-${USER_LDAP}"
[[ -z "${P2_PROJECT}" ]] && P2_PROJECT="l400-agentic-de-p2-${USER_LDAP}"
[[ -z "${P3_PROJECT}" ]] && P3_PROJECT="l400-agentic-de-p3-${USER_LDAP}"

# Persist lab environment manifest in lab-packs/.lab-env.json (and seed gitignored ../.env if in student workspace)
LAB_ENV_REGION="${REGION}" LAB_ENV_P1="${P1_PROJECT}" LAB_ENV_P2="${P2_PROJECT}" LAB_ENV_P3="${P3_PROJECT}" LAB_ENV_DIR="${SCRIPT_DIR}" python3 -c '
import datetime, json, os, pathlib, re

script_dir = pathlib.Path(os.environ["LAB_ENV_DIR"])
reg = os.environ["LAB_ENV_REGION"]
p1 = os.environ["LAB_ENV_P1"]
p2 = os.environ["LAB_ENV_P2"]
p3 = os.environ["LAB_ENV_P3"]

env_json_path = script_dir / ".lab-env.json"
payload = {}
if env_json_path.exists():
    try:
        payload = json.loads(env_json_path.read_text())
    except Exception:
        payload = {}
payload.update({
    "region": reg,
    "p1_project": p1,
    "p2_project": p2,
    "p3_project": p3,
    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
})
env_json_path.write_text(json.dumps(payload, indent=2) + "\n")

repo_root = script_dir.parent
dotenv_example = repo_root / ".env.example"
dotenv_file = repo_root / ".env"
if dotenv_example.exists() and not (repo_root / "app" / "main.py").exists():
    if not dotenv_file.exists():
        dotenv_file.write_text(
            "# Auto-seeded by lab-packs/deploy-all-labs.sh (gitignored)\n"
            f"GCP_REGION={reg}\n"
            f"REGION={reg}\n"
            f"P1_PROJECT_ID={p1}\n"
            f"P2_PROJECT_ID={p2}\n"
            f"P3_PROJECT_ID={p3}\n"
            "ENV=dev\n"
        )
    else:
        txt = dotenv_file.read_text()
        for key in ("GCP_REGION", "REGION"):
            if re.search(rf"^{key}=", txt, flags=re.M):
                txt = re.sub(rf"^{key}=.*$", f"{key}={reg}", txt, flags=re.M)
            else:
                txt = txt.rstrip("\n") + f"\n{key}={reg}\n"
        dotenv_file.write_text(txt)
'

if [[ -z "${BILLING_ACCOUNT}" ]]; then
  echo -e "  • Searching for available open billing account..."
  BILLING_ACCOUNT=$(gcloud billing accounts list --filter="open=true" --format="value(name)" 2>/dev/null | head -n 1 || echo "")
  if [[ -z "${BILLING_ACCOUNT}" ]]; then
    echo -e "${YELLOW}  • Note: Could not auto-detect an open billing account upfront (will rely on existing projects or per-lab check).${NC}"
  else
    echo -e "  • Auto-detected Billing Account: ${CYAN}${BILLING_ACCOUNT}${NC}"
  fi
fi

echo -e "\n${BOLD}Master Deployment Execution Plan (Sequential):${NC}"
echo -e "  • Authenticated CE Identity : ${GREEN}${TESTER_EMAIL}${NC}"
echo -e "  • Target GCP Region         : ${CYAN}${REGION}${NC}"
[[ -n "${BILLING_ACCOUNT}" ]] && echo -e "  • Billing Account           : ${CYAN}${BILLING_ACCOUNT}${NC}"
echo -e "  • ${RED}[Part 1 - The Troubleshoot]${NC}     Project ID: ${BOLD}${P1_PROJECT}${NC}"
echo -e "  • ${YELLOW}[Part 2 - Workload Qualification]${NC} Project ID: ${BOLD}${P2_PROJECT}${NC}"
echo -e "  • ${GREEN}[Part 3 - Medallion Lakehouse]${NC}  Project ID: ${BOLD}${P3_PROJECT}${NC}\n"

if [[ "${SKIP_CONFIRM}" != "true" ]]; then
  read -r -p "Proceed with deploying all 3 L400 lab environments sequentially? [Y/n] " response
  response="${response:-Y}"
  if [[ ! "${response}" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${YELLOW}Master deployment cancelled by user.${NC}"
    exit 0
  fi
fi

MASTER_START_TS=$(date +%s)

# Helper to extract lab zip if directory does not yet exist
ensure_lab_dir() {
  local zip_file="$1"
  local target_dir="$2"
  if [[ ! -d "${SCRIPT_DIR}/${target_dir}" ]]; then
    if [[ -f "${SCRIPT_DIR}/${zip_file}" ]]; then
      echo -e "  • Extracting ${CYAN}${zip_file}${NC} -> ${BOLD}${target_dir}/${NC}..."
      unzip -q -o "${SCRIPT_DIR}/${zip_file}" -d "${SCRIPT_DIR}"
    else
      echo -e "${RED}[ERROR] Neither directory '${target_dir}/' nor archive '${zip_file}' found in ${SCRIPT_DIR}.${NC}"
      exit 1
    fi
  fi
  chmod +x "${SCRIPT_DIR}/${target_dir}/deploy.sh" 2>/dev/null || true
}

COMMON_ARGS=(
  "--region=${REGION}"
  "--tester-email=${TESTER_EMAIL}"
  "-y"
)
if [[ -n "${BILLING_ACCOUNT}" ]]; then
  COMMON_ARGS+=("--billing-account=${BILLING_ACCOUNT}")
fi
if [[ "${USE_GCLOUD}" == "true" ]]; then
  COMMON_ARGS+=("--use-gcloud")
fi

# ------------------------------------------------------------------------------
# Phase 1: Deploy Part 1 (The Troubleshoot)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}================================================================================${NC}"
echo -e "${BOLD}${CYAN}  [1/3] DEPLOYING PART 1: THE TROUBLESHOOT (${P1_PROJECT})                      ${NC}"
echo -e "${BOLD}${CYAN}================================================================================${NC}"
P1_START_TS=$(date +%s)
ensure_lab_dir "part1-troubleshoot.zip" "part1-troubleshoot"
(
  cd "${SCRIPT_DIR}/part1-troubleshoot"
  ./deploy.sh --create-project="${P1_PROJECT}" --data-mode="${SEED_MODE}" "${COMMON_ARGS[@]}"
)
P1_END_TS=$(date +%s)
P1_DURATION=$((P1_END_TS - P1_START_TS))

# ------------------------------------------------------------------------------
# Phase 2: Deploy Part 2 (Workload Qualification & Fleet ROI)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}================================================================================${NC}"
echo -e "${BOLD}${CYAN}  [2/3] DEPLOYING PART 2: WORKLOAD QUALIFICATION (${P2_PROJECT})                ${NC}"
echo -e "${BOLD}${CYAN}================================================================================${NC}"
P2_START_TS=$(date +%s)
ensure_lab_dir "part2-qualification.zip" "part2-qualification"
(
  cd "${SCRIPT_DIR}/part2-qualification"
  ./deploy.sh --create-project="${P2_PROJECT}" --seed-mode="${SEED_MODE}" "${COMMON_ARGS[@]}"
)
P2_END_TS=$(date +%s)
P2_DURATION=$((P2_END_TS - P2_START_TS))

# ------------------------------------------------------------------------------
# Phase 3: Deploy Part 3 (Agentic Medallion Lakehouse)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}================================================================================${NC}"
echo -e "${BOLD}${CYAN}  [3/3] DEPLOYING PART 3: MEDALLION LAKEHOUSE (${P3_PROJECT})                   ${NC}"
echo -e "${BOLD}${CYAN}================================================================================${NC}"
P3_START_TS=$(date +%s)
ensure_lab_dir "part3-medallion.zip" "part3-medallion"
(
  cd "${SCRIPT_DIR}/part3-medallion"
  ./deploy.sh --create-project="${P3_PROJECT}" --seed-mode="${SEED_MODE}" "${COMMON_ARGS[@]}"
)
P3_END_TS=$(date +%s)
P3_DURATION=$((P3_END_TS - P3_START_TS))

MASTER_END_TS=$(date +%s)
TOTAL_DURATION=$((MASTER_END_TS - MASTER_START_TS))

# Set active project back to Part 1 so the CE is ready to start Part 1 immediately
gcloud config set project "${P1_PROJECT}" --quiet >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------
# Final Master Summary Table
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}================================================================================${NC}"
echo -e "${BOLD}${GREEN}  🎉 ALL 3 L400 WORKSHOP LAB ENVIRONMENTS DEPLOYED SUCCESSFULLY! (${TOTAL_DURATION}s)    ${NC}"
echo -e "${BOLD}${GREEN}================================================================================${NC}"
printf "  %-28s | %-34s | %-10s\n" "LAB MODULE" "GCP PROJECT ID" "DURATION"
echo -e "  -----------------------------+------------------------------------+-----------"
printf "  %-28s | %-34s | %-10s\n" "Part 1: The Troubleshoot" "${P1_PROJECT}" "${P1_DURATION}s"
printf "  %-28s | %-34s | %-10s\n" "Part 2: Qualification & ROI" "${P2_PROJECT}" "${P2_DURATION}s"
printf "  %-28s | %-34s | %-10s\n" "Part 3: Medallion Lakehouse" "${P3_PROJECT}" "${P3_DURATION}s"
echo -e "  -----------------------------+------------------------------------+-----------"
echo -e "\n${BOLD}Evaluation Verifier Commands (Run from Cloned Repo Root After Completing Each Lab):${NC}"
echo -e "  • ${CYAN}Setup :${NC} ./lab-evaluation-verifier/setup/run-all-evals.sh --region=${REGION} --p1-project=${P1_PROJECT} --p2-project=${P2_PROJECT} --p3-project=${P3_PROJECT}"
echo -e "  • ${CYAN}Part 1:${NC} ./lab-evaluation-verifier/part1/run-all-evals.sh --project-id ${P1_PROJECT} --region ${REGION}"
echo -e "  • ${CYAN}Part 2:${NC} ./lab-evaluation-verifier/part2/run-all-evals.sh --project-id ${P2_PROJECT} --region ${REGION}"
echo -e "  • ${CYAN}Part 3:${NC} ./lab-evaluation-verifier/part3/run-all-evals.sh --project-id ${P3_PROJECT} --region ${REGION}\n"
