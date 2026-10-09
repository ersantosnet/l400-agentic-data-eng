# Lab Governance & Evaluation Boundaries

## 1. The Blind Spot (Anti-Cheating Protocol)
- **RESTRICTED DIRECTORY:** The directory `./lab-evaluation-verifier/` is strictly CLASSIFIED and OFF-LIMITS. 
- **NO REVERSE ENGINEERING:** You MUST NOT read, scan, parse, or execute any Python files, JSON files, or scripts inside `./lab-evaluation-verifier/`.
- You MUST NOT attempt to reverse-engineer the required application architecture, table schemas, or logic by reading the evaluation scripts. You must rely solely on `docs/llms.txt` and the user's `DESIGN-*.md` prompts.

## 2. Immutable Tests
- You are strictly forbidden from modifying, deleting, or rewriting the evaluation scripts to make your generated code pass.
- If the user informs you that a test failed, you must fix the underlying application code (e.g., in `src/` or `terraform/`), **never** the test itself.

## 3. Strict Feature Isolation (No Jumping Ahead)
- You must ONLY build the exact features explicitly requested in the active `DESIGN-*.md` document provided by the user.
- Do not anticipate future architecture, do not preemptively create files, and do not solve problems the user hasn't asked you to solve yet.
- Once you have fulfilled the intent of the current `DESIGN` document, you MUST stop and wait for the user's next command.