# Graph Report - agentic-solution-template  (2026-09-02)

## Corpus Check
- Corpus is ~46,889 words - fits in a single context window. You may not need a graph.

## Summary
- 369 nodes · 696 edges · 28 communities (15 shown, 8 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.88)
- Token cost: 500 input · 400 output

## Community Hubs (Navigation)
- Terraform Root Module & Variables
- Core Infrastructure & Networking
- Skill Creator Evaluation Framework
- GCP API Enablement
- Skill Optimization & Run Scripts
- Eval Viewer & Review Tools
- BigQuery Stored Procedures & Routines
- Colab Enterprise Notebook Creation
- Colab Notebook Deployment
- IAM & Service Accounts
- Benchmark Aggregation & Metrics
- Skill Packaging & Validation
- Architecture Diagram & Ideas
- GCP Project Provisioning
- Deployment Automation Script
- System Initialization Module
- Environment Cleanup Script
- Non-Admin Deployment Script
- Org Policies Teardown
- Org Policies Provisioning
- Project Changelog
- Contribution Guidelines
- Graphify CLI Workflow

## God Nodes (most connected - your core abstractions)
1. `var.project_id` - 39 edges
2. `module.resources` - 27 edges
3. `var.project_id` - 22 edges
4. `module.sql-scripts` - 22 edges
5. `module.deploy-notebooks-module-create-files` - 17 edges
6. `module.deploy-notebooks-module-deploy` - 17 edges
7. `module.service-account` - 15 edges
8. `module.project` - 14 edges
9. `local.local_project_id` - 14 edges
10. `Skill Creator System` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Progressive Disclosure Pattern` --semantically_similar_to--> `Domain Routing System`  [INFERRED] [semantically similar]
  .agents/skills/skill-creator/SKILL.md → AGENTS.md
- `Eval and Benchmark Iteration Loop` --semantically_similar_to--> `Autonomous Self-Correction Loop`  [INFERRED] [semantically similar]
  .agents/skills/skill-creator/SKILL.md → AGENTS.md
- `Antigravity CLI (AGY) System Instructions` --references--> `LLMs System Architecture and Context Specification`  [EXTRACTED]
  AGENTS.md → docs/llms.txt
- `Agent Routing Symlinks Configuration` --conceptually_related_to--> `Domain Routing System`  [INFERRED]
  Using-This-Template.md → AGENTS.md
- `Autonomous Template Scaffolding Prompt` --references--> `Authors and Contributors Registry`  [EXTRACTED]
  Using-This-Template-Prompt.md → AUTHORS.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Skill Creator Evaluation and Benchmarking Suite** — _agents_skills_skill_creator_agents_grader_grader_agent, _agents_skills_skill_creator_agents_comparator_blind_comparator_agent, _agents_skills_skill_creator_agents_analyzer_post_hoc_analyzer_agent, _agents_skills_skill_creator_eval_viewer_viewer_eval_viewer_ui [EXTRACTED 1.00]
- **Agentic Intent-Driven Routing Architecture** — agents_antigravity_system_instructions, _ai_rules_agent_skills_standards_agent_skills_python_standards, _ai_rules_terraform_standards_argolis_terraform_standards, docs_llms_system_architecture_context_spec [EXTRACTED 1.00]
- **Template Scaffolding and Bootstrap Lifecycle** — using_this_template_prompt_autonomous_scaffolding_prompt, using_this_template_template_setup_guide, using_this_template_agent_routing_symlinks, using_this_template_prompt_string_replacement_order_rule [EXTRACTED 1.00]
- **Architecture Ideas Collection** — images_architecture_architecture, images_architecture_idea_1, images_architecture_idea_2, images_architecture_idea_3, images_architecture_idea_4, images_architecture_idea_5 [EXTRACTED 1.00]

## Communities (28 total, 8 thin omitted)

### Community 0 - "Terraform Root Module & Variables"
Cohesion: 0.11
Nodes (56): local.code_bucket, local.dataflow_staging_bucket, local.DEMO-NAME-UNDERSCORE_bucket, local.local_impersonation_account, local.local_project_id, module.apis-batch-enable, module.deploy-notebooks-module-create-files, module.deploy-notebooks-module-deploy (+48 more)

### Community 1 - "Core Infrastructure & Networking"
Cohesion: 0.11
Nodes (44): data.google_client_config.current, google_bigquery_connection.biglake_connection, google_bigquery_connection.vertex_ai_connection, google_bigquery_dataset.google_bigquery_dataset_DEMO-NAME-UNDERSCORE, google_compute_firewall.subnet_firewall_rule, google_compute_network.default_network, google_compute_router_nat.nat-config-distinct-regions, google_compute_router.nat-router-distinct-regions (+36 more)

### Community 2 - "Skill Creator Evaluation Framework"
Cohesion: 0.06
Nodes (41): Benchmark Results Analyzer, Post-hoc Analyzer Agent, Blind Comparator Agent, Content and Structure Evaluation Rubric, Claim Extraction and Verification Engine, Grader Agent, Eval Review HTML Template, Eval Viewer Web Interface (+33 more)

### Community 3 - "GCP API Enablement"
Cohesion: 0.10
Nodes (40): google_project_service.geminidataanalytics, google_project_service.iam, google_project_service.iamcredentials, google_project_service.knowledgegraph, google_project_service.managedkafka, google_project_service.service-aiplatform, google_project_service.service-analyticshub, google_project_service.service-artifactregistry (+32 more)

### Community 4 - "Skill Optimization & Run Scripts"
Cohesion: 0.12
Nodes (27): generate_html(), main(), Generate HTML report from loop output data. If auto_refresh is True, adds a…, _call_claude(), improve_description(), main(), Path, Run `claude -p` with the prompt on stdin and return the text response. Prompt… (+19 more)

### Community 5 - "Eval Viewer & Review Tools"
Cohesion: 0.15
Nodes (19): build_run(), embed_file(), find_runs(), _find_runs_recursive(), generate_html(), get_mime_type(), _kill_port(), load_previous_iteration() (+11 more)

### Community 6 - "BigQuery Stored Procedures & Routines"
Cohesion: 0.14
Nodes (21): data.google_client_config.current, google_bigquery_routine.clean_llmgemini_pro_result_as_json_json, google_bigquery_routine.gemini_pro_result_as_string, google_bigquery_routine.initialize, null_resource.call_sp_initialize, var.appengine_region, var.bigquery_DEMO-NAME-UNDERSCORE_dataset, var.bigquery_non_multi_region (+13 more)

### Community 7 - "Colab Enterprise Notebook Creation"
Cohesion: 0.21
Nodes (17): data.google_client_config.current, google_dataform_repository.notebook_repo, local.colab_enterprise_notebooks, local_file.local_file_colab_enterprise_notebooks, local_file.local_file_colab_enterprise_notebooks_base64, local.notebook_names, var.bigquery_DEMO-NAME-UNDERSCORE_dataset, var.dataflow_service_account (+9 more)

### Community 8 - "Colab Notebook Deployment"
Cohesion: 0.17
Nodes (15): data.google_client_config.current, local.DEMO-NAME-UNDERSCORE_notebooks, local.notebook_names, null_resource.commit_DEMO-NAME-UNDERSCORE_notebooks, var.bigquery_DEMO-NAME-UNDERSCORE_dataset, var.dataflow_service_account, var.dataflow_staging_bucket, var.dataform_region (+7 more)

### Community 9 - "IAM & Service Accounts"
Cohesion: 0.35
Nodes (13): google_organization_iam_member.organization, google_project_iam_member.gcp_account_owner, google_project_iam_member.impersonation_account_owner, google_project_iam_member.service_account_cloud_function_v2, google_project_iam_member.service_account_owner, google_service_account_iam_member.service_account_impersonation, google_service_account.service_account, output.deployment_service_account (+5 more)

### Community 10 - "Benchmark Aggregation & Metrics"
Cohesion: 0.23
Nodes (12): aggregate_results(), calculate_stats(), generate_benchmark(), generate_markdown(), load_run_results(), main(), Path, Aggregate run results into summary statistics. Returns run_summary with stats… (+4 more)

### Community 11 - "Skill Packaging & Validation"
Cohesion: 0.31
Nodes (8): main(), package_skill(), Path, Check if a path should be excluded from packaging., Package a skill folder into a .skill file. Args: skill_path: Path to the skill…, should_exclude(), Basic validation of a skill, validate_skill()

### Community 12 - "Architecture Diagram & Ideas"
Cohesion: 0.33
Nodes (6): Architecture Diagram, Idea 1, Idea 2, Idea 3, Idea 4, Idea 5

### Community 13 - "GCP Project Provisioning"
Cohesion: 0.60
Nodes (5): google_project.project, output.output-project-number, var.billing_account, var.org_id, var.project_id

### Community 14 - "Deployment Automation Script"
Cohesion: 0.50
Nodes (3): deploy.sh script, TF_LOG, TF_LOG_PATH

## Knowledge Gaps
- **67 isolated node(s):** `clean-up.sh script`, `deploy-use-existing-project-non-org-admin.sh script`, `deploy.sh script`, `TF_LOG`, `TF_LOG_PATH` (+62 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 110 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `clean-up.sh script`, `deploy-use-existing-project-non-org-admin.sh script`, `deploy.sh script` to the rest of the system?**
  _67 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Terraform Root Module & Variables` be split into smaller, more focused modules?**
  _Cohesion score 0.1119177253478524 - nodes in this community are weakly interconnected._
- **Should `Core Infrastructure & Networking` be split into smaller, more focused modules?**
  _Cohesion score 0.10909090909090909 - nodes in this community are weakly interconnected._
- **Should `Skill Creator Evaluation Framework` be split into smaller, more focused modules?**
  _Cohesion score 0.06219512195121951 - nodes in this community are weakly interconnected._
- **Should `GCP API Enablement` be split into smaller, more focused modules?**
  _Cohesion score 0.0951219512195122 - nodes in this community are weakly interconnected._
- **Should `Skill Optimization & Run Scripts` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `Eval Viewer & Review Tools` be split into smaller, more focused modules?**
  _Cohesion score 0.14855072463768115 - nodes in this community are weakly interconnected._