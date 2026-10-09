I have just cloned a base project template. I need you to execute the scaffolding setup autonomously. 

First, ask me for the "Demo Name". Wait for my response. 

Once I provide the demo name, convert my input into two formats:
1. `kebab-case` (e.g., if I say "My Demo", format it as `my-demo`)
2. `snake_case` (e.g., if I say "My Demo", format it as `my_demo`)

After you have those two formats, execute the following steps in this EXACT order:

### Step 1: Global Search and Replace
Use your file editing capabilities to perform a workspace-wide find and replace. 
- ORDER IS CRITICAL. You MUST do the underscore replacement first.
- First, find all instances of `DEMO-NAME-UNDERSCORE` and replace them with the `snake_case` version of the demo name.
- Second, find all instances of `DEMO-NAME` and replace them with the `kebab-case` version of the demo name.

### Step 2: Directory Renaming
- Locate the directory `sql-scripts/DEMO-NAME-UNDERSCORE` (or what it was just renamed to in Step 1). 
- Rename this directory to match the `snake_case` version of the demo name.

### Step 3: Symlink Creation
Run the following commands in the terminal at the root of the workspace to set up our Agentic routing:
`ln -s AGENTS.md .cursorrules`
`ln -s AGENTS.md .clinerules`
`ln -s AGENTS.md CLAUDE.md`
`ln -s AGENTS.md GEMINI.md`

### Step 4: Content Updates & Placeholders
- Search the workspace for the string `REPLACE-ME`. Provide me with a list of files where this string still exists so I know what manual text I need to write.
- Update `README.md` and `AUTHORS.md` with the new demo name. 
- Check `initialize.sql` and ensure it reflects the new demo name.
- Print a prominent reminder in the chat for me to manually replace `Architecture.png`.

### Step 5: Architecture Verification
Ensure the following base directories exist (`.ai-rules/`, `docs/requirements/`, `evals/`, `graphify-out/`). If they do not exist, create them as empty directories to enforce our Agentic Configuration standards.

Do not ask for permission between steps. Execute the entire pipeline and report back when finished.