#!/usr/bin/env python3
"""
Run all 3 Lab Setup deployment evaluations (Part 1, Part 2, Part 3) in sequential order.

Usage:
  ./run-all-evals.py --p1-project=l400-agentic-de-p1-$USER --p2-project=l400-agentic-de-p2-$USER --p3-project=l400-agentic-de-p3-$USER
  Optional: --region us-central1  --no-submit  --manual
Project IDs default to l400-agentic-de-pN-$USER (or $P1_PROJECT_ID / $P2_PROJECT_ID / $P3_PROJECT_ID).
"""

import os
import re
import sys
import glob
import time
import subprocess


def parse_projects() -> dict:
    user = re.sub(r"[^a-z0-9-]", "-", os.environ.get("USER", "your-ldap").lower()).strip("-") or "your-ldap"
    projects = {n: os.environ.get(f"P{n}_PROJECT_ID") or f"l400-agentic-de-p{n}-{user}" for n in (1, 2, 3)}
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        for n in (1, 2, 3):
            flag = f"--p{n}-project"
            if arg == flag and i + 1 < len(argv):
                projects[n] = argv[i + 1].strip()
            elif arg.startswith(flag + "="):
                projects[n] = arg.split("=", 1)[1].strip()
    return projects


def passthrough_args() -> list:
    out = []
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in ("--no-submit", "--manual") or arg.startswith("--region="):
            out.append(arg)
        elif arg == "--region" and i + 1 < len(argv):
            out.extend([arg, argv[i + 1]])
    return out


def main() -> int:
    start = time.time()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    projects = parse_projects()
    scripts = sorted(glob.glob(os.path.join(script_dir, "0[1-3]-test_*.py")))

    print("=======================================================")
    print(" L400 Lab Setup Evaluator • 3 Lab Deployment Checks")
    for n in (1, 2, 3):
        print(f"  Part {n}: {projects[n]}")
    print("=======================================================\n")

    summary = []
    for script in scripts:
        part_num = int(os.path.basename(script)[1])
        cmd = [sys.executable, script, "--project-id", projects[part_num]] + passthrough_args()
        sys.stdout.flush()
        rc = subprocess.run(cmd).returncode
        summary.append((part_num, os.path.basename(script), rc == 0))
        print("")

    print("=======================================================")
    print(" Lab Setup Summary")
    for part_num, name, ok in summary:
        print(f"  {'✔ PASS' if ok else '✗ FAIL'}  0{part_num} • Part {part_num} ({projects[part_num]})  [{name}]")
    all_ok = bool(summary) and all(ok for _, _, ok in summary)
    print("=======================================================")
    if all_ok:
        print("✔ L400-SETUP-GATE-PASS • All 3 lab environments are deployed correctly.")
    else:
        print("✗ L400-SETUP-GATE-FAIL • Fix the failed checks above, then re-run this evaluator.")
    print(f"Elapsed: {time.time() - start:.1f}s")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
