# Architecture traceability

| Diagram | Component | Status | Repository evidence | Responsibility | Deployment |
|---|---|---|---|---|---|
| 00 | Axiom platform | IMPLEMENTED | `frontend/src/app/router.jsx`; `backend/app/main.py` | Delivery intelligence and governed AI | Amplify/CloudFront + ECS |
| 01 | React/Vite frontend | IMPLEMENTED | `frontend/package.json`; `frontend/src/main.jsx` | Browser application | Amplify or S3/CloudFront |
| 01 | FastAPI backend | IMPLEMENTED | `backend/app/main.py` | Authenticated API and lifecycle | ECS Fargate |
| 01 | SQLAlchemy/Alembic | IMPLEMENTED | `backend/app/database/`; `backend/alembic/versions/` | Durable schema and persistence | RDS PostgreSQL |
| 02 | AWS edge | PARTIALLY_IMPLEMENTED | `infrastructure/terraform/environments/staging/main.tf` | Static delivery and API edge | CloudFront/S3; WAF/ACM proposed |
| 02 | ECS and ECR | IMPLEMENTED | same | Container execution and registry | AWS staging |
| 02 | Operations security services | PROPOSED | no implementation file | Detection, compliance and recovery | Target AWS account |
| 03 | VPC/subnets/routes | IMPLEMENTED | Terraform staging | Network isolation and egress | eu-west-2, two AZs |
| 03 | RDS private access | IMPLEMENTED | Terraform staging | Relational persistence | Private data subnets |
| 04 | Router and shell | IMPLEMENTED | `frontend/src/app/router.jsx`; `frontend/src/components/layout/EnterpriseLayout.jsx` | Feature composition | Browser |
| 04 | Typed API/SSE boundary | IMPLEMENTED | `frontend/src/services/`; `frontend/src/store/runtime.reducer.ts` | Data transport and reconciliation | Browser to API |
| 05 | API routers | IMPLEMENTED | `backend/app/main.py`; `backend/app/api/` | HTTP contracts | ECS task |
| 05 | Delivery services | IMPLEMENTED | `backend/app/delivery/` | Domain intelligence | ECS task |
| 05 | Shared controls | IMPLEMENTED | `backend/app/auth/`; `backend/app/security/`; `backend/app/audit/` | Enforcement and evidence | ECS/PostgreSQL |
| 06 | Runtime Execution Service | IMPLEMENTED | `backend/app/services/runtime_execution_service.py` | Durable runtime coordination | ECS task |
| 06 | Orchestrator/planner | IMPLEMENTED | `backend/app/runtime/orchestrator.py`; `backend/app/planners/` | Plan and execute work | ECS task |
| 06 | Atomic runtime events | IMPLEMENTED | `backend/alembic/versions/a1c3e5f7b9d2_atomic_runtime_event_sequence.py` | Conflict-safe event ordering | PostgreSQL |
| 07 | Agent registry/versioning | IMPLEMENTED | `backend/app/agents/`; `backend/app/database/models/agent.py` | Governed agents | ECS/PostgreSQL |
| 07 | Tool discovery/native/MCP | IMPLEMENTED | `backend/app/tool_discovery/`; `backend/app/tool_sdk/`; `backend/app/mcp_integration/` | Governed capability execution | ECS/external |
| 08 | Delivery aggregate | IMPLEMENTED | `backend/app/database/models/delivery.py` | Portfolio-to-work data | PostgreSQL |
| 08 | Governance/audit aggregate | IMPLEMENTED | `backend/app/database/models/governance.py`; `audit.py` | Policy, cost, evaluation and audit | PostgreSQL |
| 09 | Cognito JWT validation | IMPLEMENTED | `backend/app/auth/cognito.py`; `backend/app/auth/dependencies.py` | Authentication and tenant claims | Cognito/ECS |
| 09 | WAF/KMS/security services | PROPOSED | no implementation file | Defense in depth | Target AWS |
| 10 | Enterprise integrations | PARTIALLY_IMPLEMENTED | `backend/app/api/integrations.py`; `backend/app/integrations/` | OAuth, sync and mappings | ECS/Secrets Manager/SaaS |
| 11 | Knowledge intelligence | IMPLEMENTED | `backend/app/knowledge_intelligence/service.py`; `backend/app/database/models/knowledge.py` | Evidence retrieval and lineage | ECS/PostgreSQL |
| 12 | Approval and Action Center | IMPLEMENTED | `backend/app/action_center/service.py`; `authorization.py` | SoD approval, execution and verification | ECS/PostgreSQL |
| 13 | Logging/metrics | PARTIALLY_IMPLEMENTED | `backend/app/logging/`; `backend/app/metrics/`; `observability/` | Operational signals | ECS/CloudWatch/configured Prometheus |
| 14 | GitHub Actions deployment | PARTIALLY_IMPLEMENTED | `.github/workflows/deploy.yml`; `postgres-migrations.yml`; `amplify.yml` | Quality and deployment | GitHub/AWS |
| 15 | Backup controls | CONFIGURED_NOT_VERIFIED | Terraform staging | RDS/S3/ECR retention | AWS staging |
| 16 | Runtime request flow | IMPLEMENTED | `backend/app/api/chat.py`; `backend/app/api/runtime.py`; runtime services | Request-to-SSE sequence | Browser/ECS/PostgreSQL |
| 17 | Copilot evidence flow | IMPLEMENTED | `backend/app/delivery/copilot_service.py`; `backend/app/delivery/repositories.py` | Authorized grounded response | ECS/PostgreSQL/model provider |
| 18 | Approved action sequence | IMPLEMENTED | `backend/app/action_center/`; `backend/app/actions/services/action_executor.py` | Human-governed mutation | ECS/PostgreSQL/adapter |

Every path above was verified to exist at generation time.
