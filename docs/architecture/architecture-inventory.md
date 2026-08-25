# Architecture inventory

Generated 2026-08-24 from Git commit `73b4a14`. Status values are `IMPLEMENTED`, `PARTIALLY_IMPLEMENTED`, `CONFIGURED_NOT_VERIFIED`, `PROPOSED`, `EXTERNAL`, and `UNKNOWN`.

| Component | Responsibility | Evidence | Runtime relationship | Data / dependencies | Boundary | Deployment | Status |
|---|---|---|---|---|---|---|---|
| React/Vite frontend | Authenticated delivery workspace | `frontend/src/app/router.jsx`; `frontend/package.json` | Calls REST and consumes SSE | Browser state; API | Browser/Cognito | Amplify and Terraform S3/CloudFront definitions coexist | IMPLEMENTED |
| FastAPI API | HTTP API and lifecycle | `backend/app/main.py` | Dispatches authenticated requests | Pydantic/SQLAlchemy | Public API to private app | ECS Fargate | IMPLEMENTED |
| Cognito authentication | Token issue and JWT verification | `backend/app/auth/cognito.py`; `infrastructure/terraform/environments/staging/main.tf` | Supplies tenant and group claims | Cognito JWKS | Identity boundary | Cognito user pool | IMPLEMENTED |
| Delivery intelligence | Portfolio, sprint, RAID, dependency and release calculations | `backend/app/delivery/` | Invoked by API services | Delivery aggregates | Tenant/entity authorization | ECS task | IMPLEMENTED |
| Runtime execution | Durable AI execution and recovery | `backend/app/services/runtime_execution_service.py`; `backend/app/runtime/` | Plans, executes, streams, resumes | Runtime executions/events | Agent/tool/model permissions | ECS task | IMPLEMENTED |
| Agent and workflow plane | Versioned definitions and governed execution | `backend/app/agents/`; `backend/app/workflows/` | Selected by runtime | Agent/workflow versions | Tenant/access policy | ECS + PostgreSQL | IMPLEMENTED |
| Tool plane | Discovery, policy and bounded invocation | `backend/app/tool_discovery/`; `backend/app/tool_sdk/`; `backend/app/mcp_integration/` | Called by workflows/agents | Catalogue/executions | Tool permissions | ECS + external endpoints | IMPLEMENTED |
| AI providers | OpenAI and Bedrock abstraction | `backend/app/ai/factory.py`; `backend/app/ai/providers/` | Model calls from governed runtime | Usage/cost/audit | Model allowlist/budget | Bedrock or outbound OpenAI | IMPLEMENTED |
| Approval and Action Center | Human approval, SoD, execution and verification | `backend/app/action_center/`; `backend/app/actions/` | Receives proposed actions | Approval/action records | Approver and adapter policy | ECS + PostgreSQL | IMPLEMENTED |
| Knowledge/evidence | Authorized evidence and cited intelligence | `backend/app/knowledge_intelligence/`; `backend/app/database/models/knowledge.py` | Supports Copilot and review | Knowledge/source versions | Authorization before retrieval | PostgreSQL | IMPLEMENTED |
| Integrations | Connections, secrets, sync, mappings and quality | `backend/app/api/integrations.py`; `backend/app/integrations/` | Polls external systems | Sync runs/source mappings | OAuth/API token scopes | ECS + Secrets Manager | PARTIALLY_IMPLEMENTED |
| Persistence | Durable relational state | `backend/app/database/models/`; `backend/alembic/versions/` | SQLAlchemy repositories | PostgreSQL | Private data boundary | RDS PostgreSQL 17 | IMPLEMENTED |
| Observability | Logs, metrics, health and audit | `backend/app/logging/`; `backend/app/metrics/`; `observability/` | Correlates requests/runtime | Logs, counters, audit | Operations boundary | CloudWatch; Prometheus/Grafana configs | PARTIALLY_IMPLEMENTED |
| CI/CD | Test, scan and deploy | `.github/workflows/`; `amplify.yml` | Builds images/artifacts and migrates | Commit/image/artifact IDs | GitHub OIDC | GitHub Actions/AWS | PARTIALLY_IMPLEMENTED |

No credential values were used or copied into this pack.
