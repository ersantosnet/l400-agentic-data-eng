#!/usr/bin/env python3
"""
Part 3 - Step 0: Planning Artifacts Pre-Flight Check (Advisory)
==============================================================
Verifies that the student (or agent) created the three canonical Stage 1-3
planning documents before or alongside code implementation:
  - P0.1: DISCOVERY.md
  - P0.2: EDA.md
  - P0.3: SPEC.md (warns if legacy PRD.md is present instead of SPEC.md)

Checks `docs/part3/<FILE>` first (canonical layout), with fallback to the
repository root `<FILE>` (or `lab-packs/part3-medallion-solution/<FILE>` when
replayed from the instructor repository and EVAL_STRICT_GCS_ONLY is not set).

Exits 0 (`✔ PASSED`) when all 3 planning docs exist, or 4 (`⚠ MISSING DOCS (Advisory)`,
treated as non-blocking in `run-all-evals.py`) when any doc is missing.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import _eval_common as ec  # noqa: E402


REQUIRED_DOCS = [
    ("P0.1", "DISCOVERY.md", "Stage 1 — Environment & Asset Discovery Document"),
    ("P0.2", "EDA.md", "Stage 2 — Exploratory Data Analysis & Chaos Audit Report"),
    ("P0.3", "SPEC.md", "Stage 3 — Medallion Architecture & Governance Specification"),
]


def resolve_doc_path(repo_root: Path, filename: str, strict_gcs_only: bool = False) -> tuple[Path | None, str]:
    """Return (resolved_path, location_label) for a planning artifact."""
    candidates = [
        (repo_root / "docs" / "part3" / filename, f"docs/part3/{filename} (canonical)"),
        (repo_root / filename, f"{filename} (repo-root fallback)"),
    ]
    if not strict_gcs_only:
        candidates.extend(
            [
                (
                    repo_root / "lab-packs" / "part3-medallion-solution" / "docs" / "part3" / filename,
                    f"lab-packs/part3-medallion-solution/docs/part3/{filename} (instructor solution fallback)",
                ),
                (
                    repo_root / "lab-packs" / "part3-medallion-solution" / filename,
                    f"lab-packs/part3-medallion-solution/{filename} (instructor solution fallback)",
                ),
            ]
        )
    for path, label in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path, label
    return None, "missing"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Part 3 Step 0: Planning Artifacts Pre-Flight Check"
    )
    parser.add_argument("--project-id", default="")
    parser.add_argument("--region", default="")
    parser.add_argument("--repo-root", default="")
    args, _ = parser.parse_known_args()

    resolved_project, _, resolved_region = ec.resolve_gcp_context(part_num=3, script_file=__file__)
    project_id = args.project_id or resolved_project or "unknown"
    region = ec.validate_region(args.region) if args.region else resolved_region

    strict_mode = ec.is_strict_gcs_only()
    script_dir = Path(__file__).resolve().parent
    repo_root = Path(args.repo_root).resolve() if args.repo_root else script_dir.parent.parent

    print("\n--- Step 0: Planning Artifacts Pre-Flight Check (Stages 1-3) ---")
    print(f"Project ID : {project_id} ({region})")
    print(f"Repo Root  : {repo_root}")

    missing = []
    for check_id, filename, description in REQUIRED_DOCS:
        found_path, label = resolve_doc_path(repo_root, filename, strict_gcs_only=strict_mode)
        if found_path is not None:
            size_bytes = found_path.stat().st_size
            print(f"  [PASS] {check_id} {filename:<14} -> found at {label} ({size_bytes} bytes)")
        else:
            if filename == "SPEC.md":
                legacy_prd, legacy_label = resolve_doc_path(repo_root, "PRD.md", strict_gcs_only=strict_mode)
                if legacy_prd is not None:
                    print(
                        f"  [WARN] {check_id} {filename:<14} -> legacy PRD.md found at {legacy_label}; "
                        "rename to docs/part3/SPEC.md (canonical Part 3 specification name)."
                    )
                else:
                    print(
                        f"  [WARN] {check_id} {filename:<14} -> NOT FOUND in docs/part3/{filename} "
                        f"({description})"
                    )
            else:
                print(
                    f"  [WARN] {check_id} {filename:<14} -> NOT FOUND in docs/part3/{filename} "
                    f"({description})"
                )
            missing.append(filename)

    if not missing:
        print(
            "[ADVISORY PRE-FLIGHT] All 3 planning artifacts (DISCOVERY.md, EDA.md, SPEC.md) verified."
        )
        sys.exit(ec.EXIT_PASS)
    else:
        print(
            f"[ADVISORY PRE-FLIGHT] Missing planning artifacts: {', '.join(missing)}. "
            "Continuing to GCP telemetry evaluation (01..07)..."
        )
        sys.exit(ec.EXIT_ADVISORY_MISSING_DOCS)


if __name__ == "__main__":
    main()
