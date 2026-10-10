#!/usr/bin/env python3
"""
Run all evaluations in sequential order.
Supports both Automatic submission (local proxy) and Manual submission (web upload).
"""

import os
import re
import sys
import glob
import json
import time
import subprocess


def get_target_project(script_dir: str) -> tuple[str, str]:
    """Resolves target GCP project_id and region from CLI args, env vars, agent-config.json, terraform.tfvars, or gcloud."""
    project_id = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or ""
    )
    region = os.environ.get("REGION") or os.environ.get("GCP_REGION") or ""

    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in ("--project-id", "--project") and i + 1 < len(argv):
            project_id = argv[i + 1].strip()
        elif arg.startswith("--project-id=") or arg.startswith("--project="):
            project_id = arg.split("=", 1)[1].strip()
        elif arg == "--region" and i + 1 < len(argv):
            region = argv[i + 1].strip()
        elif arg.startswith("--region="):
            region = arg.split("=", 1)[1].strip()

    cfg_candidates = (
        "agent-config.json",
        "../agent-config.json",
        "../../agent-config.json",
        os.path.join(script_dir, "../../agent-config.json"),
    )
    for cfg_path in cfg_candidates:
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    project_id = project_id or cfg.get("gcp-project-id", "")
                    region = (
                        region
                        or cfg.get("primary-region")
                        or cfg.get("bigquery-region")
                        or cfg.get("cloud-run-region")
                        or cfg.get("artifact-registry-location", "")
                    )
            except Exception:
                pass

    if not project_id:
        tfvars_candidates = (
            "terraform/terraform.tfvars",
            "../terraform/terraform.tfvars",
            "../../terraform/terraform.tfvars",
            os.path.join(script_dir, "../../terraform/terraform.tfvars"),
        )
        for tfvars_path in tfvars_candidates:
            if os.path.exists(tfvars_path):
                try:
                    with open(tfvars_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    m_proj = re.search(r'project_id\s*=\s*"([^"]+)"', content)
                    if m_proj and m_proj.group(1) and "your-" not in m_proj.group(1):
                        project_id = m_proj.group(1).strip()
                    m_reg = re.search(r'region\s*=\s*"([^"]+)"', content)
                    if m_reg and not region:
                        region = m_reg.group(1).strip()
                except Exception:
                    pass

    if not project_id or project_id == "null":
        try:
            res = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
                project_id = res.stdout.strip()
        except Exception:
            pass

    return project_id or "unknown", region or "us-central1"


def main():
    suite_start = time.time()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = sorted(glob.glob(os.path.join(script_dir, "[0-9][0-9]-*.py")))

    if not scripts:
        print(f"No evaluation scripts found in {script_dir}")
        sys.exit(1)

    project_id, region = get_target_project(script_dir)

    print("================================================================================")
    print(f" Running All Lab Evaluations ({len(scripts)} scripts)")
    print(f" Target Project : {project_id} ({region})")
    print("================================================================================")

    results = []
    for script in scripts:
        script_name = os.path.basename(script)
        print("\n--------------------------------------------------------------------------------")
        print(f"Running: {script_name} | Project: {project_id} ({region})")
        print("--------------------------------------------------------------------------------")
        t0 = time.time()
        cmd = [sys.executable, script] + sys.argv[1:]
        ret = subprocess.run(cmd)
        elapsed = time.time() - t0
        results.append((script_name, ret.returncode, elapsed))

    total_elapsed = time.time() - suite_start

    print("\n================================================================================")
    print(f" Evaluation Run Summary (Project: {project_id})")
    print("================================================================================")
    all_passed = True
    for sname, code, elapsed in results:
        status = f"COMPLETED ({elapsed:.2f}s)" if code == 0 else f"FAILED (exit code {code}, {elapsed:.2f}s)"
        if code != 0:
            all_passed = False
        print(f"  {sname:<44} : {status}")
    print("--------------------------------------------------------------------------------")
    print(f"  {'Target Project':<44} : {project_id} ({region})")
    print(f"  {'Total Elapsed Time':<44} : {total_elapsed:.2f}s")
    print("================================================================================")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
