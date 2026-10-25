#!/usr/bin/env python3
"""
Run all Part 3 evaluations in sequential order.
Supports both Automatic submission (Cloud Run validator) and Manual submission (web upload).
"""

import glob
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec  # noqa: E402

ec.apply_default_gcp_env()


def get_target_project() -> tuple[str, str]:
    """Resolves target GCP project_id and region via _eval_common.resolve_gcp_context."""
    project_id, _, region = ec.resolve_gcp_context(part_num=3, script_file=__file__)
    return project_id or "unknown", region


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = sorted(glob.glob(os.path.join(script_dir, "[0-9][0-9]-*.py")))

    if not scripts:
        print(f"No evaluation scripts found in {script_dir}")
        sys.exit(1)

    project_id, region = get_target_project()

    print("================================================================================")
    print(f" Running All Lab Evaluations ({len(scripts)} scripts)")
    print(f" Target Project : {project_id} ({region})")
    print("================================================================================")

    forward_args = list(sys.argv[1:])
    has_proj_flag = any(
        a in ("--project-id", "--project") or a.startswith(("--project-id=", "--project="))
        for a in forward_args
    )
    has_reg_flag = any(
        a == "--region" or a.startswith("--region=")
        for a in forward_args
    )
    if not has_reg_flag and region:
        forward_args = ["--region", region] + forward_args
    if not has_proj_flag and project_id and project_id != "unknown":
        forward_args = ["--project-id", project_id] + forward_args

    results = []
    for script in scripts:
        script_name = os.path.basename(script)
        print("\n--------------------------------------------------------------------------------")
        print(f"Running: {script_name} | Project: {project_id} ({region})")
        print("--------------------------------------------------------------------------------")
        t0 = time.time()
        cmd = [sys.executable, script] + forward_args
        try:
            ret_code = subprocess.run(cmd, stdin=subprocess.DEVNULL, timeout=300).returncode
        except subprocess.TimeoutExpired:
            ret_code = 124
        elapsed = time.time() - t0
        results.append((script_name, ret_code, elapsed))

    summary_text, all_passed = ec.format_eval_summary(
        project_id=project_id,
        region=region,
        script_results=results,
        title="Part 3 Evaluation Run Summary",
        gate_prefix="L400-EVAL-GATE",
    )
    print(summary_text)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
