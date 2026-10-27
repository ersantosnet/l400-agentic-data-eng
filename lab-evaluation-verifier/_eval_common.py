#!/usr/bin/env python3
"""
Shared evaluation verdict parser, dual-account identity/subprocess helpers,
regional context resolver, .zstd event log decompression, and summary table
formatter for L400 evaluators (`setup/`, `part1/`, `part2/`, `part3/`).

Standardized Exit Code Contract (Zero `COMPLETED` Strings):
  0 -> Execution: EXECUTED | Evaluation Result: ✔ PASSED
  2 -> Execution: EXECUTED | Evaluation Result: ✗ FAILED
  3 -> Execution: EXECUTED | Evaluation Result: ⚠ FAILED (Manual / Ungraded)
  4 -> Execution: EXECUTED | Evaluation Result: ⚠ MISSING DOCS (Advisory)
  1 -> Execution: ERROR    | Evaluation Result: ✗ FAILED (Script Error)
"""

from __future__ import annotations

import getpass
import glob
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

os.environ.setdefault("CLOUDSDK_CORE_DISABLE_PROMPTS", "1")

LAB = "L400-agentic-data-eng"
DEFAULT_VALIDATOR_URL = os.environ.get(
    "VALIDATOR_URL",
    os.environ.get("URL", "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app"),
)
SALT = os.environ.get("EVAL_SIGNATURE_SALT", "argolis-eval-verifier-salt-2026")
DEFAULT_REGION = "us-central1"
GCP_REGION_REGEX = re.compile(r"^[a-z]+-[a-z]+[0-9]{1,2}$")

EXIT_PASS = 0
EXIT_SCRIPT_ERROR = 1
EXIT_EVAL_FAIL = 2
EXIT_MANUAL_UNGRADED = 3
EXIT_ADVISORY_MISSING_DOCS = 4

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


# ---------------------------------------------------------------------------
# CLI flag, region validation & GCP context resolution helpers
# ---------------------------------------------------------------------------

def validate_region(region: str) -> str:
    """Validates GCP region format against ^[a-z]+-[a-z]+[0-9]{1,2}$ or exits with code 1."""
    cleaned = (region or "").strip()
    if not GCP_REGION_REGEX.match(cleaned):
        print(
            f"Error: Invalid GCP region '{region}'. Expected format like 'us-central1' or 'europe-west1'.",
            file=sys.stderr,
        )
        sys.exit(EXIT_SCRIPT_ERROR)
    return cleaned


def parse_dotenv_file(dotenv_path: str) -> dict[str, str]:
    """Parses simple KEY=VALUE / export KEY=VALUE pairs from an un-sourced .env file."""
    parsed: dict[str, str] = {}
    if not dotenv_path or not os.path.isfile(dotenv_path):
        return parsed
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                else:
                    val = val.split("#", 1)[0].strip()
                if key and val and "your-gcp-project-id" not in val:
                    parsed[key] = val
    except Exception:
        pass
    return parsed


def is_strict_gcs_only(argv: list[str] | None = None) -> bool:
    """Returns True when local instructor/script file fallbacks must be disabled."""
    args = argv if argv is not None else sys.argv[1:]
    if os.environ.get("EVAL_STRICT_GCS_ONLY") == "1":
        return True
    return any(a in ("--strict-gcs-only", "--no-local-fallback") for a in args)


def get_gcp_account_override(argv: list[str] | None = None) -> str:
    """Resolves explicit GCP data-plane account from CLI flags or environment."""
    args = argv if argv is not None else sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("--gcp-account", "--account") and i + 1 < len(args):
            return args[i + 1].strip()
        if arg.startswith("--gcp-account=") or arg.startswith("--account="):
            return arg.split("=", 1)[1].strip()
    return (
        os.environ.get("EVAL_GCP_ACCOUNT")
        or os.environ.get("CLOUDSDK_CORE_ACCOUNT")
        or ""
    ).strip()


def build_gcp_subprocess_env(gcp_account: str = "") -> dict[str, str]:
    """Builds a non-interactive environment for data-plane gcloud/bq subprocesses."""
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    metrics_env = env.get("CLOUDSDK_METRICS_ENVIRONMENT", "")
    if "datacloud.jetski" not in metrics_env:
        env["CLOUDSDK_METRICS_ENVIRONMENT"] = f"{metrics_env} datacloud.jetski".strip()

    acct = (gcp_account or get_gcp_account_override()).strip()
    if acct:
        env["CLOUDSDK_CORE_ACCOUNT"] = acct
        if "altostrat.com" in acct.lower():
            env["CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE"] = "false"
    return env


def build_validator_token_env() -> dict[str, str]:
    """Builds an environment for minting @google.com Cloud Run identity tokens.

    Strips CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE and CLOUDSDK_CORE_ACCOUNT
    so Cloudtop ECP mTLS works natively for @google.com accounts even when the
    active data-plane account is an Argolis (*.altostrat.com) identity.
    """
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    env.pop("CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE", None)
    env.pop("CLOUDSDK_CORE_ACCOUNT", None)
    return env


def apply_default_gcp_env() -> None:
    """Applies non-interactive and account overrides to os.environ for child calls."""
    os.environ["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    acct = get_gcp_account_override()
    if acct:
        os.environ["CLOUDSDK_CORE_ACCOUNT"] = acct
        if "altostrat.com" in acct.lower():
            os.environ["CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE"] = "false"


def resolve_gcp_context(
    part_num: int | None = None,
    default_dataset: str = "",
    script_file: str = "",
    argv: list[str] | None = None,
    fallback_default_project: bool = False,
) -> tuple[str, str, str]:
    """Resolves (project_id, dataset, region) with strict multi-source precedence:

      1. CLI flags (--project-id, --project, --p{N}-project, --region)
      2. Part-specific process env var (P{N}_PROJECT_ID; BIGQUERY_DATASET; REGION -> GCP_REGION)
      3. When not is_strict_gcs_only() and part_num in (1, 2, 3):
         a. Part-specific .lab-env.json (p{N}_project, or project_id in lab-packs/part{N}-*/.lab-env.json)
         b. Part-specific un-sourced .env file (P{N}_PROJECT_ID)
         c. Part-specific lab-packs/part{N}-*/terraform/terraform.tfvars (project_id, region)
      4. Generic process env vars (PROJECT_ID -> GCP_PROJECT -> GCP_PROJECT_ID -> GOOGLE_CLOUD_PROJECT)
      5. When not is_strict_gcs_only():
         a. Generic .lab-env.json (project_id when no p1/p2/p3_project keys exist, region)
         b. Generic un-sourced .env file (PROJECT_ID / GCP_PROJECT, BIGQUERY_DATASET, REGION / GCP_REGION)
         c. agent-config.json (gcp-project-id, bigquery-dataset, primary-region / bigquery-region / ...)
         d. Generic terraform/terraform.tfvars scan (project_id if unset, region if unset)
      6. Fallback project_id: l400-agentic-de-p{N}-$USER (when fallback_default_project=True)
         or `gcloud config get-value project`
      7. Region validated against GCP_REGION_REGEX (defaults to 'us-central1').
    """
    apply_default_gcp_env()
    args = argv if argv is not None else sys.argv[1:]

    cli_project = ""
    cli_region = ""
    part_flag = f"--p{part_num}-project" if part_num in (1, 2, 3) else ""

    for i, arg in enumerate(args):
        if arg in ("--project-id", "--project") and i + 1 < len(args):
            cli_project = args[i + 1].strip()
        elif arg.startswith("--project-id=") or arg.startswith("--project="):
            cli_project = arg.split("=", 1)[1].strip()
        elif part_flag and arg == part_flag and i + 1 < len(args):
            cli_project = args[i + 1].strip()
        elif part_flag and arg.startswith(part_flag + "="):
            cli_project = arg.split("=", 1)[1].strip()
        elif arg == "--region" and i + 1 < len(args):
            cli_region = args[i + 1].strip()
        elif arg.startswith("--region="):
            cli_region = arg.split("=", 1)[1].strip()

    if cli_region:
        validate_region(cli_region)

    part_env_project = ""
    if part_num in (1, 2, 3):
        part_env_project = (os.environ.get(f"P{part_num}_PROJECT_ID") or "").strip()

    generic_env_project = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or ""
    ).strip()

    dataset = (os.environ.get("BIGQUERY_DATASET") or "").strip()
    env_region = (os.environ.get("REGION") or os.environ.get("GCP_REGION") or "").strip()

    project_id = cli_project or part_env_project
    region = cli_region or env_region

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_dir = os.path.dirname(os.path.abspath(script_file)) if script_file else os.path.dirname(os.path.abspath(__file__))

    if not is_strict_gcs_only(args):
        # 3a. Part-specific .lab-env.json & .env & terraform.tfvars lookup BEFORE generic PROJECT_ID env var
        lab_env_candidates: list[str] = [
            ".lab-env.json",
            "../.lab-env.json",
            "../../.lab-env.json",
            "lab-packs/.lab-env.json",
            "../lab-packs/.lab-env.json",
            "../../lab-packs/.lab-env.json",
            os.path.join(repo_root, ".lab-env.json"),
            os.path.join(repo_root, "lab-packs/.lab-env.json"),
        ]
        part_lab_env_candidates: list[str] = []
        if part_num in (1, 2, 3):
            for match in sorted(glob.glob(f"lab-packs/part{part_num}-*/.lab-env.json")):
                if "-solution" not in match:
                    part_lab_env_candidates.append(match)
            for match in sorted(glob.glob(os.path.join(repo_root, f"lab-packs/part{part_num}-*/.lab-env.json"))):
                if "-solution" not in match:
                    part_lab_env_candidates.append(match)

        dotenv_candidates = [
            ".env",
            "../.env",
            "../../.env",
            os.path.join(repo_root, ".env"),
        ]

        if part_num in (1, 2, 3) and not project_id:
            seen_part_le: set[str] = set()
            for le_path in lab_env_candidates + part_lab_env_candidates:
                abs_p = os.path.abspath(le_path)
                if abs_p in seen_part_le or not os.path.isfile(abs_p):
                    continue
                seen_part_le.add(abs_p)
                try:
                    with open(abs_p, "r", encoding="utf-8") as f:
                        le_data = json.load(f)
                    if not isinstance(le_data, dict):
                        continue
                    p_val = str(le_data.get(f"p{part_num}_project") or "").strip()
                    if p_val:
                        project_id = p_val
                    elif le_path in part_lab_env_candidates:
                        generic_p = str(le_data.get("project_id") or "").strip()
                        if generic_p:
                            project_id = generic_p
                    if not region:
                        r_val = str(le_data.get("region") or "").strip()
                        if r_val:
                            region = r_val
                    if project_id:
                        break
                except Exception:
                    pass

        if part_num in (1, 2, 3):
            seen_part_de: set[str] = set()
            for de_path in dotenv_candidates:
                abs_p = os.path.abspath(de_path)
                if abs_p in seen_part_de or not os.path.isfile(abs_p):
                    continue
                seen_part_de.add(abs_p)
                de_vars = parse_dotenv_file(abs_p)
                if not de_vars:
                    continue
                if not dataset and de_vars.get("BIGQUERY_DATASET"):
                    dataset = de_vars["BIGQUERY_DATASET"]
                if not region:
                    region = de_vars.get("REGION") or de_vars.get("GCP_REGION") or ""
                if not project_id and de_vars.get(f"P{part_num}_PROJECT_ID"):
                    project_id = de_vars[f"P{part_num}_PROJECT_ID"].strip()
                if project_id and region and dataset:
                    break

        if part_num in (1, 2, 3) and not project_id:
            part_tfvars_candidates: list[str] = []
            for match in sorted(glob.glob(f"lab-packs/part{part_num}-*/terraform/terraform.tfvars")):
                if "-solution" not in match:
                    part_tfvars_candidates.append(match)
            for match in sorted(glob.glob(os.path.join(repo_root, f"lab-packs/part{part_num}-*/terraform/terraform.tfvars"))):
                if "-solution" not in match:
                    part_tfvars_candidates.append(match)
            seen_part_tf: set[str] = set()
            for tfvars_path in part_tfvars_candidates:
                abs_p = os.path.abspath(tfvars_path)
                if abs_p in seen_part_tf or not os.path.isfile(abs_p):
                    continue
                seen_part_tf.add(abs_p)
                try:
                    with open(abs_p, "r", encoding="utf-8") as f:
                        content = f.read()
                    m_proj = re.search(r'project_id\s*=\s*"([^"]+)"', content)
                    if m_proj and m_proj.group(1) and "your-" not in m_proj.group(1):
                        project_id = m_proj.group(1).strip()
                    if not region:
                        m_reg = re.search(r'region\s*=\s*"([^"]+)"', content)
                        if m_reg and m_reg.group(1):
                            region = m_reg.group(1).strip()
                    if project_id:
                        break
                except Exception:
                    pass

        # 4. Generic process env vars (PROJECT_ID, GCP_PROJECT, etc.)
        if not project_id and generic_env_project:
            project_id = generic_env_project

        # 5a. Generic .lab-env.json lookup
        seen_paths: set[str] = set()
        for le_path in lab_env_candidates + part_lab_env_candidates:
            abs_p = os.path.abspath(le_path)
            if abs_p in seen_paths or not os.path.isfile(abs_p):
                continue
            seen_paths.add(abs_p)
            try:
                with open(abs_p, "r", encoding="utf-8") as f:
                    le_data = json.load(f)
                if not isinstance(le_data, dict):
                    continue
                if not project_id:
                    if part_num in (1, 2, 3):
                        p_val = str(le_data.get(f"p{part_num}_project") or "").strip()
                        if p_val:
                            project_id = p_val
                        elif not any(le_data.get(f"p{k}_project") for k in (1, 2, 3)):
                            # Single-part .lab-env.json without p1/p2/p3 keys
                            generic_p = str(le_data.get("project_id") or "").strip()
                            if generic_p:
                                project_id = generic_p
                    else:
                        generic_p = str(le_data.get("project_id") or "").strip()
                        if generic_p:
                            project_id = generic_p
                if not region:
                    r_val = str(le_data.get("region") or "").strip()
                    if r_val:
                        region = r_val
            except Exception:
                pass

        # 5b. Un-sourced .env file lookup
        for de_path in dotenv_candidates:
            abs_p = os.path.abspath(de_path)
            if abs_p in seen_paths or not os.path.isfile(abs_p):
                continue
            seen_paths.add(abs_p)
            de_vars = parse_dotenv_file(abs_p)
            if not de_vars:
                continue
            if not project_id:
                if part_num in (1, 2, 3) and de_vars.get(f"P{part_num}_PROJECT_ID"):
                    project_id = de_vars[f"P{part_num}_PROJECT_ID"]
                elif not (part_num in (1, 2, 3) and any(de_vars.get(f"P{k}_PROJECT_ID") for k in (1, 2, 3))):
                    project_id = (
                        de_vars.get("PROJECT_ID")
                        or de_vars.get("GCP_PROJECT")
                        or de_vars.get("GCP_PROJECT_ID")
                        or de_vars.get("GOOGLE_CLOUD_PROJECT")
                        or ""
                    )
            if not dataset and de_vars.get("BIGQUERY_DATASET"):
                dataset = de_vars["BIGQUERY_DATASET"]
            if not region:
                region = de_vars.get("REGION") or de_vars.get("GCP_REGION") or ""

        # 5c. agent-config.json lookup
        cfg_candidates = [
            "agent-config.json",
            "../agent-config.json",
            "../../agent-config.json",
            os.path.join(script_dir, "../../agent-config.json"),
            os.path.join(repo_root, "agent-config.json"),
        ]
        for cfg_path in cfg_candidates:
            abs_p = os.path.abspath(cfg_path)
            if abs_p in seen_paths or not os.path.isfile(abs_p):
                continue
            seen_paths.add(abs_p)
            try:
                with open(abs_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if isinstance(cfg, dict):
                    project_id = project_id or str(cfg.get("gcp-project-id") or "").strip()
                    dataset = dataset or str(cfg.get("bigquery-dataset") or "").strip()
                    region = (
                        region
                        or str(cfg.get("primary-region") or "").strip()
                        or str(cfg.get("bigquery-region") or "").strip()
                        or str(cfg.get("cloud-run-region") or "").strip()
                        or str(cfg.get("artifact-registry-location") or "").strip()
                    )
            except Exception:
                pass

        # 5d. Unconditional terraform.tfvars scan (runs whenever project_id OR region is still unset)
        if not project_id or not region:
            tfvars_candidates: list[str] = [
                "terraform/terraform.tfvars",
                "../terraform/terraform.tfvars",
                "../../terraform/terraform.tfvars",
                os.path.join(script_dir, "../../terraform/terraform.tfvars"),
                os.path.join(repo_root, "terraform/terraform.tfvars"),
            ]
            if part_num in (1, 2, 3):
                for match in sorted(glob.glob(f"lab-packs/part{part_num}-*/terraform/terraform.tfvars")):
                    if "-solution" not in match:
                        tfvars_candidates.append(match)
                for match in sorted(glob.glob(os.path.join(repo_root, f"lab-packs/part{part_num}-*/terraform/terraform.tfvars"))):
                    if "-solution" not in match:
                        tfvars_candidates.append(match)

            for tfvars_path in tfvars_candidates:
                abs_p = os.path.abspath(tfvars_path)
                if abs_p in seen_paths or not os.path.isfile(abs_p):
                    continue
                seen_paths.add(abs_p)
                try:
                    with open(abs_p, "r", encoding="utf-8") as f:
                        content = f.read()
                    if not project_id:
                        m_proj = re.search(r'project_id\s*=\s*"([^"]+)"', content)
                        if m_proj and m_proj.group(1) and "your-" not in m_proj.group(1):
                            project_id = m_proj.group(1).strip()
                    if not region:
                        m_reg = re.search(r'region\s*=\s*"([^"]+)"', content)
                        if m_reg and m_reg.group(1):
                            region = m_reg.group(1).strip()
                except Exception:
                    pass
    else:
        if not project_id and generic_env_project:
            project_id = generic_env_project

    if not project_id or project_id == "null":
        if fallback_default_project and part_num in (1, 2, 3):
            user = re.sub(r"[^a-z0-9-]", "-", os.environ.get("USER", "your-ldap").lower()).strip("-") or "your-ldap"
            project_id = f"l400-agentic-de-p{part_num}-{user}"
        else:
            try:
                res = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                    env=build_gcp_subprocess_env(),
                )
                if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
                    project_id = res.stdout.strip()
            except Exception:
                pass

    validated_region = validate_region(region or DEFAULT_REGION)
    return project_id, (dataset or default_dataset), validated_region


def resolve_zip_path(script_file: str, zip_filename: str) -> str:
    """Resolves output directory for bundle .zip (supports isolated EVAL_OUTPUT_DIR)."""
    out_dir = os.environ.get("EVAL_OUTPUT_DIR", "").strip()
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, zip_filename)
    return os.path.join(os.path.dirname(os.path.abspath(script_file)), zip_filename)


def safe_json_loads(text: str, default=None):
    """Safely decodes JSON text, returning default if empty or invalid."""
    if not text or not str(text).strip():
        return default if default is not None else {}
    try:
        return json.loads(text)
    except Exception:
        return default if default is not None else {"raw_output": str(text).strip()}


# ---------------------------------------------------------------------------
# Identity, Token & Bundle Submission
# ---------------------------------------------------------------------------

def extract_ldap(account_str: str) -> str:
    """Extracts base corporate LDAP identity from Google email or Argolis account."""
    if not account_str:
        return ""
    acc = str(account_str).strip().lower()
    if "@" not in acc:
        return acc
    user, domain = acc.split("@", 1)
    if "altostrat.com" in domain:
        parts = domain.split(".")
        if parts[0] != "altostrat":
            return parts[0]
        return user
    return user


def is_service_account(acc: str) -> bool:
    """Checks if an account string represents a GCP service account rather than a human user."""
    if not acc:
        return False
    acc_lower = str(acc).strip().lower()
    return (
        "gserviceaccount.com" in acc_lower
        or "cloudtop" in acc_lower
        or acc_lower.startswith("service-")
    )


def get_identity_token() -> tuple[str, str]:
    """Retrieves a Google identity token for Cloud Run validator authentication.

    Prioritizes an authenticated @google.com account using clean ECP mTLS env so
    Cloud Run invoker permissions succeed even when an Argolis account is active.
    """
    pre_minted_tok = os.environ.get("EVAL_VALIDATOR_TOKEN", "").strip()
    preferred_validator_acc = os.environ.get("EVAL_VALIDATOR_ACCOUNT", "").strip()
    if pre_minted_tok:
        return pre_minted_tok, (preferred_validator_acc or "pre-minted@google.com")
    if os.environ.get("EVAL_TOKEN_CHECKED") == "1":
        return "", ""

    token_env = build_validator_token_env()
    fast_candidates: list[str] = []
    if preferred_validator_acc:
        fast_candidates.append(preferred_validator_acc)

    detected_users: list[str] = []
    for u in (
        os.environ.get("USER", ""),
        os.environ.get("LOGNAME", ""),
        os.path.basename(os.path.expanduser("~")),
    ):
        u_clean = u.strip()
        if u_clean and u_clean not in detected_users:
            detected_users.append(u_clean)
    try:
        gu = getpass.getuser().strip()
        if gu and gu not in detected_users:
            detected_users.append(gu)
    except Exception:
        pass

    for u_clean in detected_users:
        user_google = u_clean if "@" in u_clean else f"{u_clean}@google.com"
        if user_google not in fast_candidates:
            fast_candidates.append(user_google)

    for google_acc in fast_candidates:
        for cert_mode in (None, "false", "true"):
            env_try = dict(token_env)
            if cert_mode is not None:
                env_try["CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE"] = cert_mode
            try:
                res = subprocess.run(
                    ["gcloud", "auth", "print-identity-token", f"--account={google_acc}"],
                    capture_output=True,
                    text=True,
                    timeout=25,
                    stdin=subprocess.DEVNULL,
                    env=env_try,
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip(), google_acc
            except Exception:
                pass

    try:
        out = subprocess.run(
            ["gcloud", "auth", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
            env=token_env,
        )
        if out.returncode == 0 and out.stdout.strip():
            accounts = json.loads(out.stdout)
            candidates = []
            for acc in accounts:
                a = acc.get("account", "")
                if a.endswith("@google.com") and a not in fast_candidates and a not in candidates:
                    candidates.append(a)
            for google_acc in candidates:
                res = subprocess.run(
                    ["gcloud", "auth", "print-identity-token", f"--account={google_acc}"],
                    capture_output=True,
                    text=True,
                    timeout=25,
                    stdin=subprocess.DEVNULL,
                    env=token_env,
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip(), google_acc
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
            env=token_env,
        )
        if res.returncode == 0 and res.stdout.strip():
            active_acc = ""
            try:
                acc_res = subprocess.run(
                    ["gcloud", "config", "get-value", "account"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                    env=token_env,
                )
                if acc_res.returncode == 0:
                    active_acc = acc_res.stdout.strip()
            except Exception:
                pass
            if active_acc and ("altostrat.com" in active_acc.lower() or "qwiklabs.net" in active_acc.lower()):
                return "", ""
            return res.stdout.strip(), active_acc
    except Exception:
        pass

    return "", ""


def get_student_identity(preferred_auth_account: str = "") -> tuple[str, str]:
    """Discovers student account & LDAP, binding to preferred_auth_account when provided."""
    explicit_ldap = (
        os.environ.get("EVAL_STUDENT_LDAP")
        or os.environ.get("STUDENT_LDAP")
        or ""
    ).strip()
    explicit_identity = os.environ.get("STUDENT_IDENTITY", "").strip()
    if explicit_ldap:
        acct = preferred_auth_account or explicit_identity or (
            explicit_ldap if "@" in explicit_ldap else f"{explicit_ldap}@google.com"
        )
        return acct, extract_ldap(explicit_ldap)

    if preferred_auth_account and not is_service_account(preferred_auth_account):
        return preferred_auth_account, extract_ldap(preferred_auth_account)

    token_env = build_validator_token_env()
    account = ""

    # 1. Search credentialed accounts in gcloud auth list (prefer @google.com then @*.altostrat.com)
    try:
        out = subprocess.run(
            ["gcloud", "auth", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=6,
            stdin=subprocess.DEVNULL,
            env=token_env,
        )
        if out.returncode == 0 and out.stdout.strip():
            accounts = json.loads(out.stdout)
            google_acc = next(
                (a["account"] for a in accounts if a.get("account", "").endswith("@google.com")),
                None,
            )
            if google_acc:
                account = google_acc
            else:
                argolis_acc = next(
                    (
                        a["account"]
                        for a in accounts
                        if "altostrat.com" in a.get("account", "")
                        and not is_service_account(a.get("account", ""))
                    ),
                    None,
                )
                if argolis_acc:
                    account = argolis_acc
                else:
                    any_user = next(
                        (a["account"] for a in accounts if not is_service_account(a.get("account", ""))),
                        None,
                    )
                    if any_user:
                        account = any_user
    except Exception:
        pass

    # 2. Fallback to active gcloud account
    if not account:
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "account"],
                capture_output=True,
                text=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "(unset)":
                candidate = result.stdout.strip()
                if not is_service_account(candidate):
                    account = candidate
        except Exception:
            pass

    # 3. Fallback to OS USER environment variable
    if not account:
        os_user = os.environ.get("USER", "").strip()
        if os_user and not is_service_account(os_user):
            account = f"{os_user}@google.com"
        else:
            account = "unknown@google.com"

    return account, extract_ldap(account)


def resolve_submission_identity(
    validator_url: str = DEFAULT_VALIDATOR_URL,
    force_manual: bool = False,
    no_submit: bool = False,
) -> tuple[str, str, str, str]:
    """Resolves (student_account, student_ldap, token, auth_account) token-first.

    Acquiring the Bearer token BEFORE signing manifest.json guarantees that
    manifest.student_ldap matches the authenticated HTTP token email, preventing
    HTTP 403 Student Identity Mismatch on multi-account workstations.
    """
    is_localhost = "localhost" in validator_url or "127.0.0.1" in validator_url
    if force_manual or no_submit or is_localhost:
        token, auth_account = "", ""
    else:
        token, auth_account = get_identity_token()
    student_account, student_ldap = get_student_identity(preferred_auth_account=auth_account)
    return student_account, student_ldap, token, auth_account


def calculate_signature(
    student_ldap: str,
    lab: str,
    evaluation: str,
    created_at: str,
    salt: str = SALT,
) -> str:
    """Generates SHA-256 signature for bundle anti-tampering."""
    raw = f"{student_ldap.strip().lower()}:{lab.strip().lower()}:{evaluation.strip().lower()}:{created_at.strip().lower()}:{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def submit_bundle(
    validator_url: str,
    zip_path: str,
    eval_name: str,
    token: str = "",
    lab: str = LAB,
    max_retries: int = 2,
) -> tuple[int, str]:
    """Submits the zip bundle to the Cloud Run validator endpoint with transient retry."""
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    filename = os.path.basename(zip_path)
    with open(zip_path, "rb") as f:
        file_bytes = f.read()

    body_parts = [
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="lab"',
        b"",
        lab.encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="evaluation"',
        b"",
        eval_name.encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        f'Content-Disposition: form-data; name="files"; filename="{filename}"'.encode("utf-8"),
        b"Content-Type: application/zip",
        b"",
        file_bytes,
        f"--{boundary}--".encode("utf-8"),
        b"",
    ]
    body = b"\r\n".join(body_parts)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "User-Agent": "lab-evaluation-client/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-User-Token"] = token

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    backoffs = [2.0, 5.0]
    last_status, last_text = 0, ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(validator_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=180) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
            last_status, last_text = e.code, err_body
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            return last_status, last_text
        except Exception as e:
            last_status = 0
            last_text = f"Failed to connect to validator at {validator_url}: {e}"
            if attempt < max_retries:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            return last_status, last_text
    return last_status, last_text


def print_manual_instructions(zip_filename: str) -> None:
    """Prints manual instructions for downloading and uploading the bundle."""
    print("=======================================================")
    print(" [Manual Submission Instructions]")
    print(f" 1. In VS Code file explorer: Right-click '{zip_filename}'")
    print(" 2. Select 'Download...' to save it to your local machine")
    print(" 3. Open the Lab Verifier Summary Portal in your browser")
    print(" 4. Click 'Manual Upload' at the top of the page")
    print(f" 5. Drag and drop '{zip_filename}' into the drop zone")
    print("=======================================================")


# ---------------------------------------------------------------------------
# Verdict parsing & per-check / suite formatting
# ---------------------------------------------------------------------------

def parse_validator_verdict(
    http_status: int,
    response_text: str,
    is_manual: bool = False,
) -> tuple[str, str, int]:
    """Parses validator HTTP status and body into (verdict, reasoning, exit_code).

    Verdicts:
      - "PASSED"   -> exit_code 0 (EXIT_PASS)
      - "FAILED"   -> exit_code 2 (EXIT_EVAL_FAIL)
      - "UNGRADED" -> exit_code 3 (EXIT_MANUAL_UNGRADED)
    """
    if is_manual:
        return (
            "UNGRADED",
            "Manual or unsubmitted mode (--manual / --no-submit); bundle was not graded by remote validator.",
            EXIT_MANUAL_UNGRADED,
        )

    if http_status == 0:
        msg = (response_text or "Validator endpoint unreachable.").strip()
        return ("UNGRADED", msg[:400], EXIT_MANUAL_UNGRADED)

    parsed = None
    if response_text and str(response_text).strip():
        try:
            parsed = json.loads(response_text)
        except Exception:
            parsed = None

    def _extract_reason(obj: dict) -> str:
        res_block = obj.get("result") if isinstance(obj.get("result"), dict) else {}
        for candidate in (
            res_block.get("reasoning"),
            res_block.get("exception"),
            obj.get("reasoning"),
            obj.get("message"),
            obj.get("error"),
            obj.get("detail"),
        ):
            if candidate and str(candidate).strip():
                return str(candidate).strip()
        return ""

    if http_status == 404:
        reason = _extract_reason(parsed) if isinstance(parsed, dict) else (response_text or "Not Found").strip()
        return ("UNGRADED", f"HTTP 404: {reason[:400]}", EXIT_MANUAL_UNGRADED)

    if http_status not in (200, 201):
        reason = _extract_reason(parsed) if isinstance(parsed, dict) else (response_text or f"HTTP {http_status}").strip()
        return ("FAILED", f"HTTP {http_status}: {reason[:400]}", EXIT_EVAL_FAIL)

    if not isinstance(parsed, dict):
        snippet = (response_text or "").strip()[:300] or "Empty or non-JSON response"
        return ("FAILED", f"Invalid non-JSON response from validator: {snippet}", EXIT_EVAL_FAIL)

    reason = _extract_reason(parsed) or "No reasoning provided."

    # 1. Primary Cloud Run schema: parsed["result"]["pass-fail"] ("PASS" | "FAIL")
    res_block = parsed.get("result")
    if isinstance(res_block, dict):
        pf = str(res_block.get("pass-fail", res_block.get("pass_fail", ""))).strip().upper()
        if pf in ("PASS", "PASSED", "SUCCESS", "OK", "TRUE"):
            return ("PASSED", reason, EXIT_PASS)
        if pf in ("FAIL", "FAILED", "ERROR", "FALSE"):
            return ("FAILED", reason, EXIT_EVAL_FAIL)
        if isinstance(res_block.get("passed"), bool):
            return (
                ("PASSED", reason, EXIT_PASS)
                if res_block["passed"]
                else ("FAILED", reason, EXIT_EVAL_FAIL)
            )

    # 2. Fallback top-level boolean: parsed["passed"]
    if isinstance(parsed.get("passed"), bool):
        return (
            ("PASSED", reason, EXIT_PASS)
            if parsed["passed"]
            else ("FAILED", reason, EXIT_EVAL_FAIL)
        )

    # 3. Fallback top-level status / verdict string
    for key in ("pass-fail", "pass_fail", "verdict", "status", "outcome"):
        val = str(parsed.get(key, "")).strip().upper()
        if val in ("PASS", "PASSED", "SUCCESS", "OK"):
            return ("PASSED", reason, EXIT_PASS)
        if val in ("FAIL", "FAILED", "ERROR"):
            return ("FAILED", reason, EXIT_EVAL_FAIL)

    # 4. Fallback checks/criteria array
    for arr_key in ("checks", "criteria", "results"):
        arr = parsed.get(arr_key)
        if isinstance(arr, list) and arr:
            all_ok = all(
                (isinstance(item, dict) and (
                    item.get("passed") is True
                    or str(item.get("status", "")).upper() in ("PASS", "PASSED", "SKIP")
                ))
                for item in arr
            )
            return (
                ("PASSED", reason, EXIT_PASS)
                if all_ok
                else ("FAILED", reason, EXIT_EVAL_FAIL)
            )

    return ("FAILED", f"Unrecognized validator response schema: {reason[:300]}", EXIT_EVAL_FAIL)


def print_remote_verdict_callout(verdict: str, reasoning: str) -> None:
    """Prints a clear bottom-line verdict callout at the end of an individual check script."""
    clean_reason = " ".join((reasoning or "").split())
    if len(clean_reason) > 320:
        clean_reason = clean_reason[:317] + "..."
    print("-------------------------------------------------------")
    if verdict == "PASSED":
        print(f" [REMOTE VERDICT] ✔ PASSED — {clean_reason}")
    elif verdict == "UNGRADED":
        print(f" [REMOTE VERDICT] ⚠ UNGRADED — {clean_reason}")
    else:
        print(f" [REMOTE VERDICT] ✗ FAILED — {clean_reason}")
    print("-------------------------------------------------------")


def finalize_check_submission(
    eval_name: str,
    zip_filename: str,
    zip_path: str,
    project_id: str,
    start_time: float,
    validator_url: str = DEFAULT_VALIDATOR_URL,
    token: str = "",
    auth_account: str = "",
    force_manual: bool | None = None,
    no_submit: bool | None = None,
    region: str = "",
) -> int:
    """Submits bundle (or handles --manual / --no-submit), prints verdict, and returns exit code."""
    if no_submit is None:
        no_submit = "--no-submit" in sys.argv or os.environ.get("NO_SUBMIT") == "1"
    if force_manual is None:
        force_manual = "--manual" in sys.argv or os.environ.get("MANUAL") == "1"
    is_localhost = "localhost" in validator_url or "127.0.0.1" in validator_url

    can_submit = not (force_manual or no_submit) and (is_localhost or bool(token))

    if can_submit:
        if token:
            acc_label = f" ({auth_account})" if auth_account else ""
            print(f"✔ Authenticated with Google Cloud identity token{acc_label}.")
        print(f"Submitting {zip_filename} to validator ({validator_url})...")
        print("")
        status, response_text = submit_bundle(validator_url, zip_path, eval_name, token)
        try:
            parsed = json.loads(response_text)
            print(json.dumps(parsed, indent=2))
        except Exception:
            print(response_text)

        verdict, reasoning, exit_code = parse_validator_verdict(status, response_text, is_manual=False)
        print_remote_verdict_callout(verdict, reasoning)

        if status not in (200, 201):
            print("")
            print("Automatic submission did not succeed. You can submit manually:")
            print_manual_instructions(zip_filename)
    else:
        if no_submit:
            print("ℹ Submission skipped (--no-submit).")
        elif force_manual:
            print("Manual submission mode requested (--manual/MANUAL=1).")
            print_manual_instructions(zip_filename)
        else:
            print("ℹ Google Cloud identity token could not be acquired (ensure 'gcloud auth login' has been run).")
            print("Proceeding with manual web submission.")
            print("")
            print_manual_instructions(zip_filename)
        verdict, reasoning, exit_code = parse_validator_verdict(0, "", is_manual=True)
        print_remote_verdict_callout(verdict, reasoning)

    elapsed = time.time() - start_time
    reg_label = f" | Region: {region}" if region else ""
    print(f"\nDone! (Project: {project_id or 'unknown'}{reg_label} | Elapsed: {elapsed:.2f}s)")
    return exit_code


def map_exit_code_to_columns(exit_code: int) -> tuple[str, str, bool]:
    """Maps a check script exit code to (execution_col, result_col, blocks_gate)."""
    if exit_code == EXIT_PASS:
        return ("EXECUTED", "✔ PASSED", False)
    if exit_code == EXIT_EVAL_FAIL:
        return ("EXECUTED", "✗ FAILED", True)
    if exit_code == EXIT_MANUAL_UNGRADED:
        return ("EXECUTED", "⚠ FAILED (Manual / Ungraded)", True)
    if exit_code == EXIT_ADVISORY_MISSING_DOCS:
        return ("EXECUTED", "⚠ MISSING DOCS (Advisory)", False)
    return ("ERROR", f"✗ FAILED (Script Error, exit {exit_code})", True)


def format_eval_summary(
    project_id: str,
    region: str,
    script_results: list[tuple[str, int, float]],
    title: str = "Evaluation Run Summary",
    gate_prefix: str = "L400-EVAL-GATE",
) -> tuple[str, bool]:
    """Formats the standardized 4-column summary table (never emitting 'COMPLETED')."""
    lines = []
    sep_eq = "=" * 88
    sep_dash = "-" * 88
    lines.append("")
    lines.append(sep_eq)
    lines.append(f" {title} (Project: {project_id} | Region: {region})")
    lines.append(sep_eq)
    lines.append(f"  {'Check':<42} {'Execution':<11} {'Evaluation Result':<25} {'Time':>6}")
    lines.append(f"  {'-' * 42} {'-' * 11} {'-' * 25} {'-' * 6}")

    total_elapsed = 0.0
    required_total = 0
    required_passed = 0
    required_failed = 0
    advisory_count = 0

    for sname, code, elapsed in script_results:
        total_elapsed += elapsed
        exec_col, res_col, blocks_gate = map_exit_code_to_columns(code)
        if code == EXIT_ADVISORY_MISSING_DOCS or sname.startswith("00-"):
            if code == EXIT_ADVISORY_MISSING_DOCS:
                advisory_count += 1
        else:
            required_total += 1
            if not blocks_gate and code == EXIT_PASS:
                required_passed += 1
            else:
                required_failed += 1
        lines.append(f"  {sname:<42} {exec_col:<11} {res_col:<25} {elapsed:>5.1f}s")

    all_passed = bool(script_results) and required_failed == 0 and required_total > 0
    lines.append(sep_dash)
    advisory_suffix = f" (plus {advisory_count} advisory notice)" if advisory_count else ""
    lines.append(
        f"  Required Checks    : {required_passed}/{required_total} PASSED, {required_failed} FAILED{advisory_suffix}"
    )
    lines.append(f"  Target Project     : {project_id} ({region})")
    lines.append(f"  Total Elapsed Time : {total_elapsed:.2f}s")
    lines.append(sep_dash)
    if all_passed:
        lines.append(
            f"  ✔ {gate_prefix}-PASS: All {required_total}/{required_total} required evaluation checks PASSED."
        )
    else:
        lines.append(
            f"  ✗ {gate_prefix}-FAIL: {required_failed} required check(s) failed evaluation. Review reasoning above."
        )
    lines.append(sep_eq)
    return "\n".join(lines), all_passed


# ---------------------------------------------------------------------------
# BigQuery, Access Token & .zstd Decompression Helpers
# ---------------------------------------------------------------------------

def run_bq_query_safe(project_id: str, sql: str, timeout: int = 120, region: str = "") -> list | dict:
    """Executes a non-interactive BigQuery SQL query with optional --location guard and fallback."""
    env = build_gcp_subprocess_env()
    base_prefix = ["bq", "--headless", "-q", f"--project_id={project_id}"]
    tail = ["query", "--use_legacy_sql=false", "--format=prettyjson", sql]

    attempts = [base_prefix + [f"--location={region}"] + tail, base_prefix + tail] if region else [base_prefix + tail]
    last_err: dict = {"error": "Unknown BigQuery query error", "returncode": 1}

    for idx, cmd in enumerate(attempts):
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
                env=env,
            )
            if p.returncode == 0:
                out = p.stdout.strip()
                if not out:
                    return []
                return json.loads(out)
            err_msg = p.stderr.strip() or p.stdout.strip()
            last_err = {"error": err_msg, "returncode": p.returncode}
            # Only fallback without --location if dataset location mismatch occurred
            if idx == 0 and len(attempts) > 1 and ("location" in err_msg.lower() or "not found" in err_msg.lower()):
                continue
            return last_err
        except subprocess.TimeoutExpired:
            return {"error": f"BigQuery query timed out after {timeout}s", "returncode": 124}
        except Exception as e:
            return {"error": str(e)}
    return last_err


def run_bq_show_json(project_id: str, table_ref: str, timeout: int = 45) -> tuple[int, dict, str]:
    """Executes a non-interactive `bq show --format=prettyjson` call with --project_id."""
    cmd = [
        "bq",
        "--headless",
        "-q",
        f"--project_id={project_id}",
        "show",
        "--format=prettyjson",
        table_ref,
    ]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=build_gcp_subprocess_env(),
        )
        if p.returncode == 0 and p.stdout.strip():
            try:
                return 0, json.loads(p.stdout), ""
            except Exception as je:
                return 1, {}, f"Invalid JSON from bq show: {je}"
        return p.returncode, {}, (p.stderr or p.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return 124, {}, f"Timed out after {timeout}s: bq show {table_ref}"
    except Exception as e:
        return 1, {}, str(e)


def get_access_token_safe() -> str:
    """Retrieves Google Cloud OAuth2 access token for REST API queries (respecting --gcp-account)."""
    env = build_gcp_subprocess_env()
    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def gcp_api_get(url: str, access_token: str, quota_project: str = "", timeout: int = 20) -> tuple[int, dict]:
    """Calls a GCP REST API GET endpoint and returns (status_code, parsed_json)."""
    headers = {"Authorization": f"Bearer {access_token}"}
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, safe_json_loads(resp.read().decode("utf-8"), {})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, safe_json_loads(err_body, {"error": err_body})
    except Exception as e:
        return 0, {"error": str(e)}


def decompress_event_log_bytes(
    raw_bytes: bytes,
    uri: str = "",
    max_chars: int = 64 * 1024 * 1024,
) -> str:
    """Decodes raw or Zstandard-compressed (.zstd) Spark event log bytes safely."""
    if not raw_bytes:
        return ""
    is_zstd = uri.lower().endswith(".zstd") or raw_bytes.startswith(ZSTD_MAGIC)
    if is_zstd:
        # 1. Try Python zstandard module if installed
        try:
            import zstandard as zstd  # type: ignore

            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(raw_bytes) as reader:
                decompressed = reader.read(max_chars)
            return decompressed.decode("utf-8", errors="replace")
        except Exception:
            pass

        # 2. Try zstd -dc or pzstd -dc CLI tools
        for binary in ("zstd", "pzstd"):
            try:
                proc = subprocess.run(
                    [binary, "-dc"],
                    input=raw_bytes,
                    capture_output=True,
                    timeout=60,
                )
                if proc.returncode == 0 and proc.stdout:
                    return proc.stdout[:max_chars].decode("utf-8", errors="replace")
            except Exception:
                continue

    return raw_bytes[:max_chars].decode("utf-8", errors="replace")
