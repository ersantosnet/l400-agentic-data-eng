#!/usr/bin/env python3
"""
Run all 3 Lab Setup deployment evaluations (Part 1, Part 2, Part 3) in sequential order.

Usage:
  ./run-all-evals.py --p1-project=l400-agentic-de-p1-$USER --p2-project=l400-agentic-de-p2-$USER --p3-project=l400-agentic-de-p3-$USER [--region us-central1]
  Optional: --region us-central1  --no-submit  --manual  --require-remote  --gcp-account <account>
Project IDs and region default to CLI args -> env vars -> .lab-env.json / .env -> l400-agentic-de-pN-$USER (us-central1).
"""

import glob
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec  # noqa: E402

ec.apply_default_gcp_env()


def parse_projects_and_region() -> tuple[dict[int, str], str]:
    """Resolves per-part project IDs and shared region via _eval_common.resolve_gcp_context."""
    # Filter out generic --project-id / --project so per-part resolution isn't shadowed unless --pN-project is passed
    clean_argv = []
    argv = sys.argv[1:]
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg in ("--project-id", "--project"):
            skip_next = True
            continue
        if arg.startswith(("--project-id=", "--project=")):
            continue
        clean_argv.append(arg)

    projects: dict[int, str] = {}
    resolved_region = ""
    for n in (1, 2, 3):
        proj_n, _, reg_n = ec.resolve_gcp_context(
            part_num=n,
            script_file=__file__,
            argv=clean_argv,
            fallback_default_project=True,
        )
        projects[n] = proj_n
        if not resolved_region:
            resolved_region = reg_n
    return projects, resolved_region or "us-central1"


def passthrough_args(region: str) -> list[str]:
    out: list[str] = []
    has_region = False
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in ("--no-submit", "--manual", "--require-remote", "--strict-gcs-only", "--no-local-fallback"):
            out.append(arg)
        elif arg.startswith("--region="):
            out.append(arg)
            has_region = True
        elif arg == "--region" and i + 1 < len(argv):
            out.extend([arg, argv[i + 1]])
            has_region = True
        elif arg.startswith(("--gcp-account=", "--account=")):
            out.append(arg)
        elif arg in ("--gcp-account", "--account") and i + 1 < len(argv):
            out.extend([arg, argv[i + 1]])
    if not has_region and region:
        out.extend(["--region", region])
    return out


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    projects, region = parse_projects_and_region()
    scripts = sorted(glob.glob(os.path.join(script_dir, "0[1-3]-test_*.py")))

    print("================================================================================")
    print(f" L400 Lab Setup Evaluator • 3 Lab Deployment Checks (Region: {region})")
    for n in (1, 2, 3):
        print(f"  Part {n}: {projects[n]} ({region})")
    print("================================================================================\n")

    extra = passthrough_args(region)
    script_results = []
    for script in scripts:
        part_num = int(os.path.basename(script)[1])
        sname = f"{os.path.basename(script)} ({projects[part_num]})"
        cmd = [sys.executable, script, "--project-id", projects[part_num]] + extra
        sys.stdout.flush()
        t0 = time.time()
        try:
            rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, timeout=300).returncode
        except subprocess.TimeoutExpired:
            rc = 124
        elapsed = time.time() - t0
        script_results.append((sname, rc, elapsed))
        print("")

    project_summary_label = f"P1={projects[1]}, P2={projects[2]}, P3={projects[3]}"
    summary_text, all_ok = ec.format_eval_summary(
        project_id=project_summary_label,
        region=region,
        script_results=script_results,
        title="Lab Setup Evaluation Summary",
        gate_prefix="L400-SETUP-GATE",
    )
    print(summary_text)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
