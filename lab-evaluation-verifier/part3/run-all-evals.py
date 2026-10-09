#!/usr/bin/env python3
"""
Run all evaluations in sequential order.
Supports both Automatic submission (local proxy) and Manual submission (web upload).
"""

import os
import sys
import glob
import subprocess


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = sorted(glob.glob(os.path.join(script_dir, "[0-9][0-9]-*.py")))

    if not scripts:
        print(f"No evaluation scripts found in {script_dir}")
        sys.exit(1)

    print("================================================================================")
    print(f" Running All Lab Evaluations ({len(scripts)} scripts)")
    print("================================================================================")

    results = []
    for script in scripts:
        script_name = os.path.basename(script)
        print("\n--------------------------------------------------------------------------------")
        print(f"Running: {script_name}")
        print("--------------------------------------------------------------------------------")
        cmd = [sys.executable, script] + sys.argv[1:]
        ret = subprocess.run(cmd)
        results.append((script_name, ret.returncode))

    print("\n================================================================================")
    print(" Evaluation Run Summary")
    print("================================================================================")
    all_passed = True
    for sname, code in results:
        status = "COMPLETED" if code == 0 else f"FAILED (exit code {code})"
        if code != 0:
            all_passed = False
        print(f"  {sname:<42} : {status}")
    print("================================================================================")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
