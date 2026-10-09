# Agentic Project Structure & Intent-Driven Engineering

Welcome to the Agentic Base Template. This repository is not just a collection of code; it is an optimized environment built for **Intent-Driven Engineering**.

In this paradigm, you shift from *manually writing code* to *designing context, constraints, and architecture*. You define the desired outcomes, boundaries, and rules in these markdown files, and you orchestrate AI Agents (like Antigravity CLI, Cursor, or Claude Code) to generate, deploy, and test the actual code.

This document explains the architecture of the workspace and how both Humans and Agents should interact with it.

---

## 🗺️ The Repository Map

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
