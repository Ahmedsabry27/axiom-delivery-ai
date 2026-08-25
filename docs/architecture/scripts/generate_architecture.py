#!/usr/bin/env python3
"""Generate the AX-ARCH-01 evidence-based architecture pack."""
from __future__ import annotations

import html
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "docs" / "architecture"
SOURCE, SVG = BASE / "source", BASE / "svg"
STATUSES = {"IMPLEMENTED": "#1f7a4d", "PARTIALLY_IMPLEMENTED": "#d97706", "CONFIGURED_NOT_VERIFIED": "#2563eb", "PROPOSED": "#64748b", "EXTERNAL": "#7c3aed", "UNKNOWN": "#b91c1c"}
AWS = "#ff9900"
TODAY = date.today().isoformat()
COMMIT = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()

def n(label, status="IMPLEMENTED", evidence="", aws=False):
    return {"label": label, "status": status, "evidence": evidence, "aws": aws}

SPECS = {
"00-platform-context": {"title":"Platform Context", "scope":"Business users, Axiom Delivery AI and trusted external systems", "state":"CURRENT + TARGET CONTEXT", "columns":[
 ["Users", n("Delivery and portfolio leadership", "EXTERNAL"), n("Programme / project / product roles", "EXTERNAL"), n("Scrum, release and risk managers", "EXTERNAL"), n("Approvers and governance administrators", "EXTERNAL")],
 ["Axiom Delivery AI", n("Delivery intelligence workspaces", evidence="frontend/src/app/router.jsx"), n("AI Copilot and evidence", evidence="backend/app/delivery/copilot_service.py"), n("Agents, workflows and governed tools", evidence="backend/app/runtime/orchestrator.py"), n("Approval and Action Center", evidence="backend/app/action_center/service.py")],
 ["Delivery SaaS", n("Jira: projects, work and sprints", "EXTERNAL"), n("Confluence: pages and evidence", "EXTERNAL"), n("Outlook / Teams via Graph", "EXTERNAL"), n("GitHub: source and delivery", "EXTERNAL")],
 ["Identity + AI", n("Amazon Cognito / identity provider", evidence="backend/app/auth/cognito.py", aws=True), n("Amazon Bedrock", "EXTERNAL", aws=True), n("OpenAI", "EXTERNAL"), n("Monitoring and notifications", "PARTIALLY_IMPLEMENTED", "backend/app/metrics/metrics.py")]],
 "edges":[[0,0,1,0,"delivery decisions"],[0,3,1,3,"review / approve"],[1,0,2,0,"synchronize"],[1,1,2,1,"authorized evidence"],[1,2,3,1,"model invocation"],[3,0,1,0,"JWT claims"]]},
"01-current-platform-architecture": {"title":"Current Platform Architecture", "scope":"Actual repository and configured AWS staging runtime", "state":"CURRENT STATE", "columns":[
 ["Browser",n("React 19 + Vite application",evidence="frontend/package.json"),n("Router, shell and feature pages",evidence="frontend/src/app/router.jsx"),n("React Query / stores / repositories",evidence="frontend/src/providers/QueryProvider.jsx"),n("Cognito auth + SSE hooks",evidence="frontend/src/services/auth.js")],
 ["FastAPI",n("API routers + auth dependencies",evidence="backend/app/main.py"),n("Delivery intelligence services",evidence="backend/app/delivery"),n("Runtime execution + recovery",evidence="backend/app/services/runtime_execution_service.py"),n("Governance / approvals / audit",evidence="backend/app/governance")],
 ["AI + capabilities",n("Planner + runtime orchestrator",evidence="backend/app/runtime/orchestrator.py"),n("Managed agents + workflows",evidence="backend/app/agents"),n("Tool discovery / native / MCP",evidence="backend/app/tool_discovery"),n("OpenAI / Bedrock abstraction",evidence="backend/app/ai/factory.py")],
 ["Persistence + AWS",n("SQLAlchemy + Alembic",evidence="backend/app/database"),n("RDS PostgreSQL 17",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("ECS Fargate + ALB",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("CloudFront / S3 and Amplify",status="CONFIGURED_NOT_VERIFIED",evidence="amplify.yml",aws=True)]],
 "edges":[[0,1,1,0,"HTTPS JSON"],[0,3,1,2,"SSE"],[1,2,2,0,"execute"],[2,0,2,1,"select"],[2,1,2,2,"invoke"],[2,3,3,2,"AWS SDK"],[1,1,3,1,"SQL / 5432"]]},
"02-target-aws-architecture": {"title":"Target AWS Reference Architecture", "scope":"Required deployment, production hardening and optional scale", "state":"TARGET STATE", "master":True,"columns":[
 ["Edge",n("Route 53 + ACM", "PROPOSED",aws=True),n("AWS WAF", "PROPOSED",aws=True),n("CloudFront",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("Private S3 frontend + OAC",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True)],
 ["Identity + API",n("Cognito user pool and claims",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("Application Load Balancer",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("ECS Fargate tasks across AZs","PROPOSED",aws=True),n("ECR immutable images",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True)],
 ["Data + AI",n("Multi-AZ RDS PostgreSQL","PROPOSED",aws=True),n("Secrets Manager",evidence="backend/app/integrations/secrets.py",aws=True),n("KMS customer-managed keys","PROPOSED",aws=True),n("Bedrock + governed models",evidence="backend/app/ai/providers/bedrock_provider.py",aws=True),n("Evidence S3 / search","PROPOSED",aws=True)],
 ["Integration + ops",n("EventBridge / SQS / DLQ","PROPOSED",aws=True),n("CloudWatch logs, metrics, alarms","PARTIALLY_IMPLEMENTED",aws=True),n("CloudTrail / Config / GuardDuty / Security Hub","PROPOSED",aws=True),n("AWS Backup + SNS","PROPOSED",aws=True),n("External Jira / Graph / OpenAI","EXTERNAL")]],
 "edges":[[0,0,0,2,"DNS + TLS"],[0,1,0,2,"filter"],[0,2,0,3,"static"],[0,2,1,1,"HTTPS"],[1,0,1,1,"JWT"],[1,1,1,2,"8080"],[1,2,2,0,"5432"],[1,2,2,1,"credentials"],[1,2,2,3,"AI"],[1,2,3,0,"async"],[3,1,3,3,"notify"]]},
"03-aws-network-architecture": {"title":"AWS Network Architecture", "scope":"eu-west-2 VPC traffic, trust boundaries and production target", "state":"CURRENT + PROPOSED HARDENING", "master":True,"columns":[
 ["Internet / edge",n("Users + external SaaS","EXTERNAL"),n("CloudFront HTTPS 443",aws=True),n("Internet Gateway",aws=True)],
 ["Public subnets AZ-a / AZ-b",n("Internet-facing ALB :80","PARTIALLY_IMPLEMENTED","infrastructure/terraform/environments/staging/main.tf",True),n("NAT Gateway AZ-a",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("Second NAT / HTTPS listener","PROPOSED",aws=True)],
 ["Private app subnets",n("ECS task AZ-a :8080",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("ECS task AZ-b + autoscaling","PROPOSED",aws=True),n("VPC endpoints: ECR, logs, secrets","PROPOSED",aws=True),n("ECS security group: ALB only",evidence="infrastructure/terraform/environments/staging/main.tf")],
 ["Private data subnets",n("RDS PostgreSQL :5432 private",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("RDS security group: ECS only",evidence="infrastructure/terraform/environments/staging/main.tf"),n("Multi-AZ standby","PROPOSED",aws=True),n("Route 53 private DNS","PROPOSED",aws=True)]],
 "edges":[[0,0,0,1,"HTTPS 443"],[0,1,1,0,"origin HTTP current"],[1,0,2,0,"SG / 8080"],[2,0,3,0,"SG / 5432"],[2,0,1,1,"egress"],[1,1,0,2,"internet"],[2,2,0,1,"AWS private APIs"]]},
"04-frontend-architecture": {"title":"Frontend Architecture", "scope":"React feature composition, state, transport and production boundaries", "state":"CURRENT STATE", "columns":[
 ["Application",n("main.jsx + QueryProvider",evidence="frontend/src/main.jsx"),n("Browser router + route error recovery",evidence="frontend/src/app/router.jsx"),n("Enterprise shell + design system",evidence="frontend/src/components/layout/EnterpriseLayout.jsx"),n("Cognito protected routes",evidence="frontend/src/auth/ProtectedRoute.jsx")],
 ["Delivery features",n("My Day / Command Center / Portfolio"),n("Sprints / Releases / RAID / Dependencies"),n("Actions / Meetings / Knowledge"),n("Copilot / ceremonies")],
 ["Automation + admin",n("Agents / workflows / approvals"),n("Integrations / MCP / tools"),n("Models / governance / AI Operations"),n("Settings / audit")],
 ["Data boundary",n("Typed services and repositories",evidence="frontend/src/services"),n("React Query + Zustand",evidence="frontend/src/store"),n("REST HTTPS + bearer JWT",evidence="frontend/src/services/api.ts"),n("SSE runtime reconciliation",evidence="frontend/src/services/runtime.service.ts"),n("Mock/API selection: dev only",evidence="frontend/src/config/deliveryDataMode.ts")]],
 "edges":[[0,1,1,0,"routes"],[0,1,2,0,"routes"],[1,0,3,0,"queries"],[2,0,3,0,"queries"],[3,0,3,2,"API"],[3,3,1,3,"events"]]},
"05-backend-service-architecture": {"title":"Backend Service Architecture", "scope":"FastAPI layering and shared enforcement", "state":"CURRENT STATE", "columns":[
 ["API",n("Routers: chat, runtime, delivery, admin",evidence="backend/app/main.py"),n("Authentication + tenant context",evidence="backend/app/auth/dependencies.py"),n("Validation + response contracts",evidence="backend/app/contracts")],
 ["Application services",n("Conversation + runtime execution",evidence="backend/app/services"),n("Sprint / RAID / dependency / release / portfolio intelligence",evidence="backend/app/delivery"),n("Meeting + knowledge intelligence",evidence="backend/app/meeting_intelligence"),n("Approvals, actions, governance, integrations",evidence="backend/app/action_center")],
 ["Domain + runtime",n("Orchestrator / planner / workflow engine",evidence="backend/app/runtime"),n("Agent registry + execution",evidence="backend/app/agents"),n("Tool discovery / native / MCP",evidence="backend/app/tool_discovery"),n("AI provider abstraction",evidence="backend/app/ai")],
 ["Persistence",n("Repositories and transactions",evidence="backend/app/repositories"),n("SQLAlchemy models",evidence="backend/app/database/models"),n("Alembic forward migrations",evidence="backend/alembic/versions"),n("PostgreSQL",evidence="backend/app/database/postgres.py")],
 ["Shared controls",n("Permissions / source authorization",evidence="backend/app/security"),n("Audit + redaction",evidence="backend/app/audit"),n("Correlation logging + metrics",evidence="backend/app/logging"),n("Budget and model governance",evidence="backend/app/governance/budget_enforcement.py")]],
 "edges":[[0,0,0,1,"Depends"],[0,1,1,0,"authorize"],[1,0,2,0,"coordinate"],[1,1,3,0,"read/write"],[2,0,2,1,"dispatch"],[2,1,2,2,"capabilities"],[3,0,3,1,"ORM"],[3,1,3,3,"SQL"],[4,0,1,1,"enforce"],[4,1,3,1,"append"]]},
"06-ai-runtime-architecture": {"title":"AI Runtime Architecture", "scope":"Durable planning, execution, interruption, streaming and governance", "state":"CURRENT STATE", "master":True,"columns":[
 ["Request",n("Copilot / Chat request"),n("Conversation validation"),n("Delivery context + evidence")],
 ["Durable runtime",n("RuntimeExecutionService",evidence="backend/app/services/runtime_execution_service.py"),n("Runtime orchestrator",evidence="backend/app/runtime/orchestrator.py"),n("Planner → execution plan",evidence="backend/app/planners"),n("Atomic event sequence",evidence="backend/alembic/versions/a1c3e5f7b9d2_atomic_runtime_event_sequence.py")],
 ["Execution",n("Agent registry + permissions",evidence="backend/app/runtime/agent_registry.py"),n("Workflow engine + tasks",evidence="backend/app/workflows"),n("Tool discovery / native / MCP",evidence="backend/app/tool_discovery"),n("WAITING_FOR_INPUT / continuation",evidence="backend/app/runtime/continuation_interpreter.py"),n("Cancellation / failure / recovery",evidence="backend/app/runtime/recovery.py")],
 ["AI governance",n("Model allowlist",evidence="backend/app/governance/service.py"),n("Budget reserve + settlement",evidence="backend/app/governance/budget_enforcement.py"),n("OpenAI or Bedrock",evidence="backend/app/ai/factory.py"),n("Evaluation + AI audit",evidence="backend/app/governance")],
 ["Events",n("Runtime event persistence",evidence="backend/app/database/models/task.py"),n("Authenticated SSE",evidence="backend/app/api/runtime.py"),n("Frontend reducer reconciliation",evidence="frontend/src/store/runtime.reducer.ts")]],
 "edges":[[0,0,0,1,"validate"],[0,1,1,0,"create"],[1,0,1,1,"coordinate"],[1,1,1,2,"plan"],[1,2,2,0,"select"],[2,0,2,1,"execute"],[2,1,2,2,"invoke"],[2,2,3,2,"model/tool"],[3,0,3,2,"allow"],[3,1,3,2,"budget"],[2,3,1,1,"continue"],[2,4,1,0,"recover"],[3,2,4,0,"result"],[4,0,4,1,"stream"],[4,1,4,2,"SSE"]]},
"07-agent-and-tool-architecture": {"title":"Agent and Tool Architecture", "scope":"Distinct governed definitions, associations and execution records", "state":"CURRENT STATE", "columns":[
 ["Agent",n("Agent definition + immutable version",evidence="backend/app/database/models/agent.py"),n("Identity, capability and model policy",evidence="backend/app/agents/models"),n("Tool / knowledge / access assignments",evidence="backend/app/database/models/agent_assignment.py")],
 ["Workflow",n("Workflow definition + version",evidence="backend/app/database/models/workflow.py"),n("Agent/tool/condition/approval nodes",evidence="backend/app/workflows"),n("Triggers and input contracts",evidence="backend/app/workflows")],
 ["Capabilities",n("Tool catalogue + discovery",evidence="backend/app/tool_discovery"),n("Native governed tools",evidence="backend/app/tool_sdk"),n("Approved MCP remote tools",evidence="backend/app/mcp_integration"),n("Model registry + allowlist",evidence="backend/app/governance/service.py")],
 ["Control + evidence",n("Runtime / agent execution records",evidence="backend/app/database/models/agent_execution.py"),n("Proposed action (not execution)",evidence="backend/app/action_center/service.py"),n("Approval → controlled adapter",evidence="backend/app/actions/services/action_executor.py"),n("Verification + audit trail",evidence="backend/app/audit")]],
 "edges":[[0,0,0,2,"assign"],[1,0,0,0,"uses"],[1,1,2,0,"nodes"],[0,2,2,0,"permissions"],[2,0,2,1,"resolve"],[2,0,2,2,"resolve"],[2,3,3,0,"model"],[0,0,3,0,"execute"],[3,0,3,1,"propose"],[3,1,3,2,"approve"],[3,2,3,3,"verify"]]},
"08-data-architecture": {"title":"Logical Data Architecture", "scope":"Tenant-owned aggregates, evidence lineage and immutable governance records", "state":"CURRENT STATE", "master":True,"columns":[
 ["Identity / hierarchy",n("Tenant → user identity reference",evidence="backend/app/database/models/user.py"),n("Portfolio → programme → project → team",evidence="backend/app/database/models/delivery.py"),n("Source integration + mapping",evidence="backend/app/database/models/integration.py")],
 ["Delivery",n("Sprint → work item → defect",evidence="backend/app/database/models/delivery.py"),n("Release → milestone",evidence="backend/app/database/models/delivery.py"),n("RAID item ↔ dependency",evidence="backend/app/database/models/delivery.py"),n("Meeting → transcript / decision / lesson",evidence="backend/app/database/models/meeting.py")],
 ["Evidence + intelligence",n("Knowledge item + source version",evidence="backend/app/database/models/knowledge.py"),n("Evidence reference + lineage",evidence="backend/app/database/models/knowledge_source.py"),n("Recommendation → proposed action",evidence="backend/app/database/models/action_center.py"),n("Approval → execution → verification",evidence="backend/app/database/models/action_center.py")],
 ["Runtime",n("Conversation → messages",evidence="backend/app/models/conversation.py"),n("Runtime execution → immutable events",evidence="backend/app/models/runtime_execution.py"),n("Agent / workflow / tool versions",evidence="backend/app/database/models/agent.py"),n("Integration sync runs / quality",evidence="backend/app/database/models/integration.py")],
 ["Governance",n("Policy / entity grant / access review",evidence="backend/app/database/models/governance.py"),n("Usage ledger / cost / budget",evidence="backend/app/database/models/governance.py"),n("Evaluation / incident",evidence="backend/app/database/models/governance.py"),n("Append-only hash-chained audit",evidence="backend/app/database/models/audit.py")]],
 "edges":[[0,0,0,1,"owns"],[0,1,1,0,"plans"],[0,2,1,0,"maps"],[1,0,1,1,"delivers"],[1,2,2,2,"recommend"],[1,3,2,0,"creates"],[2,0,2,1,"versions"],[2,2,2,3,"govern"],[3,0,3,1,"executes"],[3,1,4,3,"audits"],[3,2,3,1,"runs"],[4,0,2,1,"authorizes"],[4,1,3,1,"limits"]]},
"09-security-and-authorization": {"title":"Security and Authorization Architecture", "scope":"Defense in depth and decision enforcement points", "state":"CURRENT + TARGET HARDENING", "columns":[
 ["Browser trust",n("Cognito sign-in / external IdP",evidence="frontend/src/services/auth.js",aws=True),n("Access token held client-side"),n("CI/CD administrator boundary","EXTERNAL")],
 ["AWS edge",n("TLS / CloudFront",aws=True),n("WAF","PROPOSED",aws=True),n("ALB security group",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True)],
 ["Application boundary",n("JWT issuer/client/token-use validation",evidence="backend/app/auth/cognito.py"),n("Tenant + role/group claims",evidence="backend/app/auth/dependencies.py"),n("Permission catalogue + entity grants",evidence="backend/app/security"),n("Source/evidence authorization",evidence="backend/app/delivery/repositories.py"),n("SoD + approval policy",evidence="backend/app/action_center/authorization.py")],
 ["Data + AI boundary",n("Private RDS + SG",aws=True),n("Secrets Manager tenant prefix",evidence="backend/app/integrations/secrets.py",aws=True),n("Model allowlist + budget",evidence="backend/app/governance"),n("KMS CMK","PROPOSED",aws=True)],
 ["Detection",n("Redacted audit trail",evidence="backend/app/audit"),n("CloudTrail / Config / GuardDuty / Security Hub","PROPOSED",aws=True),n("CloudWatch alerts","PARTIALLY_IMPLEMENTED",aws=True)]],
 "edges":[[0,0,1,0,"HTTPS"],[1,0,2,0,"bearer JWT"],[2,0,2,1,"claims"],[2,1,2,2,"tenant/role"],[2,2,2,3,"before retrieval"],[2,2,2,4,"before action"],[2,2,3,0,"authorized SQL"],[2,4,4,0,"decision audit"],[3,1,2,3,"credential ref"],[3,2,4,0,"usage audit"]]},
"10-integration-architecture": {"title":"Integration Architecture", "scope":"Provider adapters, OAuth, synchronization and controlled write-back", "state":"CURRENT + PROPOSED DURABILITY", "columns":[
 ["Axiom framework",n("Integration catalogue + connection",evidence="backend/app/api/integrations.py"),n("Secret reference / Secrets Manager",evidence="backend/app/integrations/secrets.py",aws=True),n("OAuth state + callback",evidence="backend/app/integrations/runtime.py"),n("Sync run, cursor, mappings, quality",evidence="backend/app/database/models/integration.py"),n("Source mapping + evidence lineage",evidence="backend/app/integrations")],
 ["Atlassian",n("Jira API token / OAuth adapter",evidence="backend/app/integrations/jira.py"),n("Confluence cloud operations",evidence="backend/app/api/integrations.py"),n("Rate limit / retry / idempotency","PARTIALLY_IMPLEMENTED"),n("Approved write-back","PARTIALLY_IMPLEMENTED")],
 ["Microsoft",n("Entra OAuth authorization",evidence="backend/app/api/integrations.py"),n("Microsoft Graph",evidence="backend/app/api/integrations.py"),n("Outlook calendar + meetings",evidence="backend/app/api/integrations.py"),n("Teams meetings / transcripts",evidence="backend/app/api/integrations.py"),n("Human review before knowledge/action",evidence="backend/app/meeting_intelligence")],
 ["AI / delivery",n("OpenAI secured outbound",evidence="backend/app/ai/providers/openai_provider.py"),n("Amazon Bedrock IAM",evidence="backend/app/ai/providers/bedrock_provider.py",aws=True),n("GitHub Actions OIDC",evidence=".github/workflows/deploy.yml"),n("SQS / EventBridge / DLQ","PROPOSED",aws=True)]],
 "edges":[[0,0,0,1,"credential"],[0,2,1,0,"Atlassian OAuth"],[0,3,1,0,"poll/sync"],[0,3,2,1,"Graph sync"],[1,0,0,4,"source map"],[2,2,2,4,"review"],[3,0,0,0,"provider"],[3,1,0,0,"provider"],[0,3,3,3,"durable async"]]},
"11-knowledge-and-evidence": {"title":"Knowledge and Evidence Architecture", "scope":"Authorized ingestion, lineage, retrieval, citation and review", "state":"CURRENT + PROPOSED SEARCH", "columns":[
 ["Authorized sources",n("Jira / Confluence / meetings","EXTERNAL"),n("Release and delivery records"),n("Knowledge and lessons")],
 ["Ingestion",n("Source authorization first",evidence="backend/app/delivery/repositories.py"),n("Sanitation + redaction",evidence="backend/app/security"),n("Content fingerprint + version",evidence="backend/app/database/models/knowledge_source.py"),n("Freshness / trust / conflict status",evidence="backend/app/knowledge_intelligence")],
 ["Knowledge graph",n("Evidence reference + source mapping",evidence="backend/app/database/models/knowledge.py"),n("Decision / lesson / meeting summary",evidence="backend/app/database/models/knowledge.py"),n("Superseded content + human verification",evidence="backend/app/knowledge_intelligence")],
 ["Retrieval + response",n("Tenant/entity authorization before ranking",evidence="backend/app/api/delivery.py"),n("SQL retrieval",evidence="backend/app/knowledge_intelligence/service.py"),n("OpenSearch/vector retrieval","PROPOSED",aws=True),n("Copilot structured response + citations",evidence="backend/app/delivery/copilot_service.py"),n("Audit",evidence="backend/app/audit")]],
 "edges":[[0,0,1,0,"authorize"],[1,0,1,1,"sanitize"],[1,1,1,2,"fingerprint"],[1,2,2,0,"version"],[2,0,3,0,"filter"],[3,0,3,1,"retrieve"],[3,1,3,3,"ground"],[3,2,3,3,"optional rank"],[3,3,3,4,"audit"]]},
"12-approval-and-action-flow": {"title":"Approval and Action Flow", "scope":"Stateful separation-of-duties control plane", "state":"CURRENT STATE", "columns":[
 ["Proposal",n("DRAFT → PROPOSED",evidence="backend/app/database/models/action_center.py"),n("Policy classification"),n("PENDING_APPROVAL")],
 ["Decision",n("Requester identity"),n("Eligible approver + SoD check",evidence="backend/app/action_center/authorization.py"),n("APPROVED / REJECTED"),n("CANCELLED")],
 ["Execution",n("EXECUTING"),n("Allowlisted controlled adapter",evidence="backend/app/actions/services/action_executor.py"),n("EXECUTED / FAILED")],
 ["Assurance",n("Independent verification",evidence="backend/app/action_center/service.py"),n("VERIFIED"),n("Audit + notification",evidence="backend/app/audit")]],
 "edges":[[0,0,0,1,"classify"],[0,1,0,2,"submit"],[0,2,1,1,"review"],[1,0,1,1,"cannot self-approve"],[1,1,1,2,"decide"],[1,2,2,0,"approved"],[1,2,1,3,"reject/cancel"],[2,0,2,1,"dispatch"],[2,1,2,2,"result"],[2,2,3,0,"verify"],[3,0,3,1,"success"],[3,1,3,2,"record"]]},
"13-observability-and-operations": {"title":"Observability and Operations", "scope":"End-to-end correlation, health, signals and incident response", "state":"CURRENT + TARGET HARDENING", "columns":[
 ["Application signals",n("Structured logs + request ID",evidence="backend/app/logging"),n("Correlation / runtime execution IDs",evidence="backend/app/runtime/tracing.py"),n("Audit events",evidence="backend/app/audit"),n("Prometheus metrics",evidence="backend/app/metrics")],
 ["AWS telemetry",n("CloudWatch Logs",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("ECS Container Insights",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("ALB / ECS / RDS health",status="CONFIGURED_NOT_VERIFIED",aws=True),n("X-Ray / OpenTelemetry","PROPOSED",aws=True)],
 ["Operations",n("Prometheus / Grafana configs",status="CONFIGURED_NOT_VERIFIED",evidence="observability/docker-compose.yml"),n("Dashboards and alarms","PARTIALLY_IMPLEMENTED"),n("SNS notifications","PROPOSED",aws=True),n("Incident records + runbooks",evidence="docs/operations-runbook.md")],
 ["Trace path",n("User request → API"),n("Runtime → provider/tool"),n("DB/audit → CloudWatch"),n("Alarm → incident → runbook")]],
 "edges":[[0,0,1,0,"ship"],[0,1,3,0,"correlate"],[3,0,3,1,"execution ID"],[3,1,3,2,"audit ID"],[3,2,3,3,"signal"],[1,0,2,1,"query"],[1,1,2,1,"metrics"],[2,1,2,2,"alarm"],[2,2,2,3,"notify"]]},
"14-cicd-deployment": {"title":"CI/CD and Deployment Architecture", "scope":"Immutable build, approvals, AWS OIDC and environment promotion", "state":"CURRENT + TARGET CONTROLS", "columns":[
 ["Source",n("Developer → branch → pull request","EXTERNAL"),n("Git commit SHA"),n("GitHub repository","EXTERNAL")],
 ["Quality gates",n("GitHub Actions",evidence=".github/workflows",aws=False),n("Frontend/backend tests + lint"),n("Gitleaks / security checks",evidence=".github/workflows/security.yml"),n("Terraform plan + approval","PARTIALLY_IMPLEMENTED")],
 ["AWS staging",n("GitHub OIDC role",evidence=".github/workflows/deploy.yml",aws=True),n("ECR image digest",aws=True),n("Alembic migration task",evidence=".github/workflows/postgres-migrations.yml",aws=True),n("ECS deployment + smoke tests",aws=True),n("Amplify frontend artifact hash",evidence="amplify.yml",aws=True)],
 ["Production target",n("Protected environment approval","PROPOSED"),n("Separate Terraform state/account","PROPOSED",aws=True),n("Production migration + ECS/CloudFront","PROPOSED",aws=True),n("Rollback images/artifacts/evidence","PARTIALLY_IMPLEMENTED")]],
 "edges":[[0,0,0,2,"PR"],[0,2,1,0,"trigger"],[1,0,1,1,"test"],[1,1,1,2,"scan"],[1,2,1,3,"plan"],[1,3,2,0,"OIDC"],[2,0,2,1,"push"],[2,1,2,2,"migrate"],[2,2,2,3,"deploy"],[2,3,2,4,"frontend"],[2,4,3,0,"promote"],[3,0,3,2,"approve"]]},
"15-backup-recovery": {"title":"Backup and Recovery", "scope":"Protected assets, restore paths and unverified recovery controls", "state":"CURRENT + PROPOSED RECOVERY", "columns":[
 ["Protected assets",n("RDS automated backups: 7 days",evidence="infrastructure/terraform/environments/staging/main.tf",aws=True),n("RDS final snapshot + prevent_destroy",aws=True),n("S3 frontend versioning",aws=True),n("ECR retains 30 images",aws=True),n("Terraform remote state",status="CONFIGURED_NOT_VERIFIED",evidence="infrastructure/terraform/environments/staging/backend.tf",aws=True)],
 ["Secrets + audit",n("Secrets Manager versions",status="CONFIGURED_NOT_VERIFIED",aws=True),n("Secret rotation","PROPOSED",aws=True),n("Audit preservation",status="PARTIALLY_IMPLEMENTED"),n("AWS Backup policy","PROPOSED",aws=True)],
 ["Recovery",n("Restore RDS to recovery environment","PROPOSED",aws=True),n("Redeploy immutable ECR/frontend artifact","PARTIALLY_IMPLEMENTED"),n("Run Alembic compatibility checks"),n("Restore validation / smoke tests","PROPOSED"),n("DNS / traffic recovery","PROPOSED",aws=True)],
 ["Decision points",n("RTO and RPO: not approved","UNKNOWN"),n("Multi-region requirement: unknown","UNKNOWN"),n("Recovery rehearsal cadence","PROPOSED"),n("Evidence and audit retention policy","PARTIALLY_IMPLEMENTED")]],
 "edges":[[0,0,2,0,"restore"],[0,2,2,1,"rollback"],[0,3,2,1,"image"],[1,0,2,1,"credentials"],[2,0,2,2,"migrate"],[2,2,2,3,"validate"],[3,0,2,0,"select point"],[3,2,2,3,"rehearse"]]},
"16-runtime-request-sequence": {"title":"Runtime Request Sequence", "scope":"Primary and alternate execution paths", "state":"CURRENT STATE", "sequence":True,"columns":[
 ["Frontend",n("1. POST Chat/Copilot"),n("11. Consume SSE"),n("12. Reconcile UI")],
 ["API + conversation",n("2. Authenticate / authorize"),n("3. Validate conversation"),n("Unauthorized → 401/403")],
 ["Runtime",n("4. Create durable execution"),n("5. Orchestrator → planner"),n("WAITING_FOR_INPUT → continue"),n("Cancel / sequence conflict guarded")],
 ["Agent / workflow",n("6. Select permitted agent"),n("7. Execute workflow/task"),n("Tool failure → failed event")],
 ["Tool / model + events",n("8. Invoke allowed tool/model"),n("Provider failure → safe error"),n("9. Persist atomic event"),n("10. Publish authenticated SSE")]],
 "edges":[[0,0,1,0,"request"],[1,0,1,1,"claims"],[1,1,2,0,"valid"],[2,0,2,1,"start"],[2,1,3,0,"plan"],[3,0,3,1,"route"],[3,1,4,0,"invoke"],[4,0,4,2,"result"],[4,2,4,3,"publish"],[4,3,0,1,"SSE"],[0,1,0,2,"reduce"]]},
"17-copilot-evidence-sequence": {"title":"Copilot Evidence Retrieval Sequence", "scope":"Authorization-before-ranking and cited response alternatives", "state":"CURRENT STATE", "sequence":True,"columns":[
 ["User / Copilot",n("1. Ask with delivery context"),n("9. Structured cited response")],
 ["Authorization",n("2. Validate JWT + tenant",evidence="backend/app/auth/dependencies.py"),n("3. Entity/source grants",evidence="backend/app/delivery/repositories.py"),n("Unauthorized → deny + audit",evidence="backend/app/api/delivery.py")],
 ["Evidence",n("4. Retrieve authorized evidence"),n("Missing evidence → explicit insufficiency"),n("5. Freshness/trust/conflict checks")],
 ["Ranking + model",n("6. Rank permitted evidence"),n("7. Governed model invocation"),n("Provider failure → graceful error")],
 ["Citation + audit",n("8. Attach evidence references"),n("Record retrieval/model/audit IDs"),n("Proposed actions remain unexecuted")]],
 "edges":[[0,0,1,0,"request"],[1,0,1,1,"claims"],[1,1,2,0,"allowed scope"],[2,0,2,2,"evidence"],[2,2,3,0,"rank"],[3,0,3,1,"grounded prompt"],[3,1,4,0,"response"],[4,0,4,1,"audit"],[4,0,0,1,"cite"]]},
"18-approved-action-sequence": {"title":"Approved Action Sequence", "scope":"Human-governed proposal, execution, verification and alternatives", "state":"CURRENT STATE", "sequence":True,"columns":[
 ["User / Copilot",n("1. Recommendation"),n("2. Create proposed action"),n("Cancellation → CANCELLED")],
 ["Policy",n("3. Classify impact / approval"),n("4. Check requester and SoD"),n("Ineligible → reject")],
 ["Approval Center",n("5. PENDING_APPROVAL"),n("6. Approver decision"),n("Rejected / changes requested")],
 ["Execution adapter",n("7. APPROVED → EXECUTING"),n("8. Allowlisted adapter"),n("Tool failure → FAILED")],
 ["Verification / audit",n("9. EXECUTED → verify"),n("10. VERIFIED or failed verification"),n("11. Immutable audit + notification")]],
 "edges":[[0,0,0,1,"propose"],[0,1,1,0,"classify"],[1,0,1,1,"policy"],[1,1,2,0,"eligible"],[2,0,2,1,"review"],[2,1,3,0,"approve"],[3,0,3,1,"execute"],[3,1,4,0,"result"],[4,0,4,1,"verify"],[4,1,4,2,"record"],[4,2,0,0,"notify"]]},
}

def esc(x): return html.escape(str(x), quote=True)

def wrap(text, limit=27):
    words, lines, current = text.split(), [], ""
    for word in words:
        if current and len(current)+len(word)+1 > limit: lines.append(current); current=word
        else: current=(current+" "+word).strip()
    if current: lines.append(current)
    return lines[:4]

def render(key, spec):
    width, height = (3840,2160) if spec.get("master") else (3200,1800)
    cols=spec["columns"]; gap=30; margin=80; top=250; bottom=180
    cw=(width-2*margin-gap*(len(cols)-1))/len(cols); area_h=height-top-bottom
    positions={}; parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
      '<defs><filter id="shadow"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-opacity=".15"/></filter><marker id="blue" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto"><path d="M0,0 L0,8 L11,4 z" fill="#2474b5"/></marker></defs>',
      '<rect width="100%" height="100%" fill="#f7f7f5"/>',
      f'<rect width="100%" height="18" fill="{AWS}"/><text x="80" y="90" font-family="Arial" font-size="48" font-weight="700" fill="#232f3e">{esc(spec["title"])}</text>',
      f'<text x="80" y="138" font-family="Arial" font-size="22" fill="#52616f">Scope: {esc(spec["scope"])}</text><text x="80" y="178" font-family="Arial" font-size="20" font-weight="700" fill="#a15c00">{esc(spec["state"])}</text>',
      f'<text x="{width-80}" y="90" text-anchor="end" font-family="Arial" font-size="18" fill="#52616f">Generated {TODAY} • Git {COMMIT}</text>']
    for ci,col in enumerate(cols):
        title,*nodes=col; x=margin+ci*(cw+gap); row_h=(area_h-70)/max(len(nodes),1)
        parts.append(f'<rect x="{x:.0f}" y="{top}" width="{cw:.0f}" height="{area_h}" rx="22" fill="#ffffff" stroke="#9aa7b2" stroke-width="2"/>')
        parts.append(f'<rect x="{x:.0f}" y="{top}" width="{cw:.0f}" height="58" rx="22" fill="#232f3e"/><text x="{x+24:.0f}" y="{top+39}" font-family="Arial" font-size="24" font-weight="700" fill="white">{esc(title)}</text>')
        for ri,node in enumerate(nodes):
            nx=x+20; ny=top+75+ri*row_h; nw=cw-40; nh=min(150,row_h-18); color=STATUSES[node["status"]]; dash=' stroke-dasharray="12 8"' if node["status"] in {"PROPOSED","UNKNOWN"} else ''
            positions[(ci,ri)]=(nx,ny,nw,nh)
            parts.append(f'<rect x="{nx:.0f}" y="{ny:.0f}" width="{nw:.0f}" height="{nh:.0f}" rx="16" fill="#fff" stroke="{color}" stroke-width="4"{dash} filter="url(#shadow)"/>')
            tx=nx+22
            if node.get("aws"):
                parts.append(f'<rect x="{nx+18:.0f}" y="{ny+18:.0f}" width="54" height="54" rx="10" fill="{AWS}"/><text x="{nx+45:.0f}" y="{ny+53:.0f}" text-anchor="middle" font-family="Arial" font-size="18" font-weight="700" fill="#232f3e">AWS</text>'); tx=nx+88
            for li,line in enumerate(wrap(node["label"], 25 if node.get("aws") else 32)):
                parts.append(f'<text x="{tx:.0f}" y="{ny+37+li*28:.0f}" font-family="Arial" font-size="{22 if li==0 else 20}" font-weight="{700 if li==0 else 400}" fill="#232f3e">{esc(line)}</text>')
            parts.append(f'<circle cx="{nx+24:.0f}" cy="{ny+nh-22:.0f}" r="8" fill="{color}"/><text x="{nx+42:.0f}" y="{ny+nh-16:.0f}" font-family="Arial" font-size="15" fill="#52616f">{node["status"]}</text>')
    for a,ar,b,br,label in spec.get("edges",[]):
        if (a,ar) not in positions or (b,br) not in positions: continue
        x,y,w,h=positions[(a,ar)]; X,Y,W,H=positions[(b,br)]; x1=x+w; y1=y+h/2; x2=X; y2=Y+H/2
        if a==b: x1=x+w*.78; x2=X+w*.78
        mid=(x1+x2)/2
        parts.append(f'<path d="M{x1:.0f},{y1:.0f} H{mid:.0f} V{y2:.0f} H{x2:.0f}" fill="none" stroke="#2474b5" stroke-width="3" marker-end="url(#blue)"/>')
        parts.append(f'<rect x="{mid-68:.0f}" y="{(y1+y2)/2-17:.0f}" width="136" height="28" rx="6" fill="#f7f7f5"/><text x="{mid:.0f}" y="{(y1+y2)/2+4:.0f}" text-anchor="middle" font-family="Arial" font-size="14" fill="#185887">{esc(label)}</text>')
    ly=height-110; parts.append(f'<text x="80" y="{ly-28}" font-family="Arial" font-size="18" font-weight="700" fill="#232f3e">Legend — solid: evidenced; dashed: proposed/unknown; blue arrows: synchronous; AWS tile: AWS service</text>')
    for i,(status,color) in enumerate(STATUSES.items()):
        x=80+i*470; parts.append(f'<circle cx="{x+8}" cy="{ly}" r="8" fill="{color}"/><text x="{x+24}" y="{ly+6}" font-family="Arial" font-size="16" fill="#232f3e">{status}</text>')
    parts.append('</svg>')
    (SVG/f"{key}.svg").write_text("\n".join(parts),encoding="utf-8")
    (SOURCE/f"{key}.json").write_text(json.dumps(spec,indent=2)+"\n",encoding="utf-8")

def contact_sheet():
    width,height=3840,2700; parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#f7f7f5"/><text x="80" y="90" font-family="Arial" font-size="48" font-weight="700" fill="#232f3e">Axiom Delivery AI — Architecture Index</text><text x="80" y="135" font-family="Arial" font-size="20" fill="#52616f">19 evidence-based views • generated {TODAY} • Git {COMMIT}</text>']
    for i,(key,spec) in enumerate(SPECS.items()):
        col=i%4; row=i//4; x=80+col*930; y=190+row*490
        parts.append(f'<rect x="{x}" y="{y}" width="870" height="420" rx="20" fill="white" stroke="#9aa7b2" stroke-width="2"/><rect x="{x}" y="{y}" width="16" height="420" fill="{AWS}"/><text x="{x+36}" y="{y+40}" font-family="Arial" font-size="23" font-weight="700" fill="#232f3e">{esc(key)} — {esc(spec["title"])}</text><image href="{key}.svg" x="{x+30}" y="{y+58}" width="820" height="342" preserveAspectRatio="xMidYMid meet"/>')
    parts.append('</svg>'); (SVG/'architecture-contact-sheet.svg').write_text("\n".join(parts),encoding='utf-8')

SOURCE.mkdir(parents=True,exist_ok=True); SVG.mkdir(parents=True,exist_ok=True)
for key,spec in SPECS.items(): render(key,spec)
contact_sheet()
print(f"Generated {len(SPECS)} diagrams at commit {COMMIT}")
