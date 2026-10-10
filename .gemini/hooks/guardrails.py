#!/usr/bin/env python3
"""
Deterministic PreToolUse Lifecycle Hook for L400 Agentic Data Engineering.
Enforces:
1. Evaluator Blind Spot (blocks access to lab-evaluation-verifier*, proxy.py, and hook self-tampering)
2. Zero Secrets Policy on git add / git commit commands
"""

import json
import re
import sys

BLIND_SPOT_PATTERNS = [
    r"lab-evaluation-verifier",
    r"(^|/|\\|\s)proxy\.py(\s|$|\"|')",
    r"\.gemini/hooks",
]

SECRET_GIT_PATTERNS = [
    r"git\s+add\s+(?:.*[\s/])?\.env(?!\.example\b)(?:\.|\s|$|\"|')",
    r"git\s+add\s+(?:.*[\s/])?(?:[^\s]*(?:service_account|credentials)[^\s]*|sa[_.\-][^\s]*|[^\s]*[_.\-]sa[_.\-][^\s]*)\.json",
    r"git\s+add\s+.*\.(?:key|pem|pkcs12|sqlite3|db-journal)(?:\s|$|\"|')",
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {}) or {}

    # 1. Check file path arguments on file tools
    target_path = args.get("AbsolutePath") or args.get("TargetFile") or ""
    for pattern in BLIND_SPOT_PATTERNS:
        if re.search(pattern, target_path):
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": (
                            f"Blocked by L400 Lab Governance Policy: '{target_path}' is part of the "
                            "protected lab evaluation infrastructure."
                        ),
                    }
                )
            )
            return

    # 2. Check shell commands on run_command
    if tool_name == "run_command":
        cmd = args.get("CommandLine", "")
        for pattern in BLIND_SPOT_PATTERNS:
            if re.search(pattern, cmd):
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": (
                                "Blocked by L400 Lab Governance Policy: Commands accessing "
                                "protected evaluation infrastructure are strictly prohibited."
                            ),
                        }
                    )
                )
                return

        for pattern in SECRET_GIT_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": (
                                "Blocked by Zero Secrets Policy: Staging secret, credential, "
                                "or local .env files to Git is prohibited."
                            ),
                        }
                    )
                )
                return

    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
