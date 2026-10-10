---
description: Mandatory rule requiring the agent to always create a structured 6-section plan and clarify ambiguities before writing code or executing cloud jobs.
trigger: always_on
---

# Mandatory Plan-First & Clarify-First Protocol

Before creating or modifying files, running destructive or state-changing commands, or submitting cloud jobs (Dataproc, BigQuery, dbt, Composer, Dataplex), you **MUST** first present a structured execution plan and wait for the user's explicit approval.

## Required Plan Sections
Every plan you present MUST contain the following six sections in order:

1. **Summary of the Plan**
   - A concise 2–3 sentence executive overview of the objective and expected outcome.
2. **What You Want to Do**
   - Bullet points describing the specific deliverables, architectural changes, or cloud operations to be performed.
3. **How You Want to Do It**
   - Step-by-step technical approach, including which Data Agent Kit (DAK) skills, MCP tools, CLI commands, and `.gemini/rules/` standards will be used.
4. **Files Expected to Change or Create**
   - Explicit list of target file paths (e.g., `src/part1/...`, `docs/part2/...`, `PRD.md`, `.gemini/rules/...`) and whether each will be created, modified, or deleted.
5. **Regression Risk Analysis**
   - Assessment of potential risks (e.g., schema incompatibility, Gluten/Velox operator fallback, 1:N join fan-out, data overwrite, cost/runtime impact) and how you will mitigate and verify them.
6. **Clarification Questions (If any)**
   - Any open questions regarding underspecified requirements, missing parameters, or uncompleted `<!-- TODO (CE): ... -->` sections in `PRD.md` or `.gemini/rules/`. If everything is clear, explicitly state *"None — ready to proceed upon your approval."*
