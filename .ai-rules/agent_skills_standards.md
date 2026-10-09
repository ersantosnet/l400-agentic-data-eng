# Agent Skills & Python Scripting Standards
**Trigger:** Read this file whenever you are asked to write a new Python script, CLI automation, or an Agent Skill (`SKILL.md` / `run.py`).

## 🌐 1. Dependency Preferences (The REST API Default)
- **Highly Preferred:** Default to using raw Google Cloud REST APIs. We do this to minimize `pip install` dependencies and keep the agent environment lightweight. Try to rely only on `google-auth` and `requests`.
- **Fallback (If Necessary):** You may use Google Cloud SDK client libraries (e.g., `google-cloud-bigquery`, `google-cloud-dataplex`) *only if necessary*. Use them if the REST implementation would be excessively complex, error-prone, or if you need to handle complex tasks like gRPC streaming or large file chunking.
- If you use a thick client library, you must explicitly add it to the skill's `requirements.txt`.

## 🛠️ 2. GCP REST API Pattern (When using the preferred method)
When interacting with Google Cloud via REST, use this exact authentication pattern:
1. Authenticate using `google.auth.default()`.
2. Generate an access token: `creds.refresh(auth_req)` -> `creds.token`.
3. Pass the token as a Bearer token in the `Authorization` header.
4. Execute the call using the `requests` library (`requests.get`, `requests.post`, etc.).

## 📂 3. Skill Directory Structure
If building a new skill for the Antigravity CLI, it must follow this exact structure:
- Path: `.agents/skills/[skill-name]/`
- `SKILL.md`: The markdown definition telling the agent how and when to use the skill.
- `scripts/run.py`: The python execution logic.
- `scripts/requirements.txt`: The required dependencies for the script.

## 📥 4. Import & Configuration Pattern (CRITICAL)
When providing the "Example Usage" inside a `SKILL.md` file, **NEVER hardcode project IDs, regions, or resource names.** 

You MUST instruct the agent to dynamically append the script path AND load its environment variables from `agent-config.json` at the workspace root. Always use this exact pattern in your `SKILL.md` examples:

```python
import sys
import os
import json

# 1. Append the skill path dynamically
sys.path.append(os.path.abspath('.agents/skills/[skill-name]/scripts'))
import run

# 2. Read the environment config (stored at the root of the project)
with open('agent-config.json', 'r') as f:
    config = json.load(f)

# 3. Call the function using config values (Example)
result = run.my_skill_function(
    project_id=config["gcp-project-id"],
    region=config["bigquery-region"]
)
print(result)