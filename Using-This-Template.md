This document specifies how to use this boilerplate template
  - To have AGY execute these steps just run @Using-This-Template-Prompt.md in the AGY CLI.

***

## 🔍 Search and Replace (In Exact Order)
You need to search and replace these values workspace-wide **in this specific order**:

1. **`DEMO-NAME-UNDERSCORE`**: (For dataset and variable names requiring an underscore) 
   *Example: `my_demo`*
2. **`DEMO-NAME`**: (For project, directory folder, and GitHub names requiring a dash) 
   *Example: `my-demo`*
3. **Rename Directory:** You must manually rename the `sql-scripts/DEMO-NAME-UNDERSCORE` folder to match your new underscore name.

---

## 📝 Other Manual Updates
- Search the workspace for **`REPLACE-ME`** and update those text blocks.
- Update the **`README.md`** and **`AUTHORS.md`**.
- Update **`initialize.sql`**.
- Replace **`Architecture.png`** with your actual architecture diagram.

---

## 🔗 Symlink Setup Commands
Run these commands from the root directory of your project (where your `AGENTS.md` file lives).

```bash
# 1. Create the symbolic links pointing to AGENTS.md
ln -s AGENTS.md .cursorrules
ln -s AGENTS.md .clinerules
ln -s AGENTS.md CLAUDE.md
ln -s AGENTS.md GEMINI.md

# 2. Verify that the links were created successfully
ls -la | grep AGENTS.md

# 3. Clean up (Run these only if you want to remove the links later)
unlink .cursorrules
unlink .clinerules
unlink CLAUDE.md
unlink GEMINI.md
```

---

## 🤖 Agentic Configurations (Review)

```text
# Agentic Project Structure

# 1. THE ROUTER & STATE
├── AGENTS.md                 # The Global Entry Point (points AI to .ai-rules/)
├── agent-config.json         # The "environment variables" for AGY to use for GCP

# 2. MODULAR GOVERNANCE & CONSTRAINTS (Progressive Disclosure)
├── .ai-rules/                
│   ├── terraform_standards.md    # Never run destroy, must use modules                 
│   ├── agent_skills_standards.md # REST API rules and Python constraints
│   └── etc/                      # Security and domain-specific rules

# 3. AGENT SKILLS & TOOLS (Executable capabilities for AGY)
├── .agents/skills/                  
│   ├── knowledge-catalog/
│   │   ├── SKILL.md              # Documentation on how AGY uses this tool
│   │   └── scripts/run.py        # The actual REST API execution logic
│   └── deploy-terraform/
│       ├── SKILL.md
│       └── scripts/run.py

# 4. INTENT & CONTEXT (Human & Machine Documentation)
├── docs/
│   ├── design/                # AI-generated Architectural Prompts & Feature Intents
│   ├── requirements/          # Raw human inputs (PDFs, transcripts, CE notes)
│   └── llms.txt               # Machine-readable project overview / API specs

# 5. AUTOMATED VERIFICATION (Evals & Definition of Done)
├── evals/                    
│   ├── prompts.json           # Test fixtures (inputs vs expected outputs)
│   └── evaluation-unit-tests/ # Test files specifically testing AI outputs

# 6. KNOWLEDGE MAP (Architectural Awareness)
├── graphify-out/             
│   ├── graph.html             # For YOU: Interactive visual map of your architecture
│   ├── GRAPH_REPORT.md        # For AI: Plain-English summary of your app's "God nodes"
│   └── graph.json             # For AI: Machine-readable relationships for AGY to query

# 7. EXECUTION LAYER (The Actual Payload)
├── src/                       # Application logic, Cloud Functions, DAGs
├── terraform/                 # Root Terraform deployment configurations
├── terraform-modules/         # Reusable Infrastructure-as-Code modules

# --- SYMLINKS (All pointing to AGENTS.md) ---
├── .cursorrules -> AGENTS.md 
├── .clinerules -> AGENTS.md
├── CLAUDE.md -> AGENTS.md    
└── GEMINI.md -> AGENTS.md 
```