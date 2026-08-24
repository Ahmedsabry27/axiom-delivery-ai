# Enterprise AI Copilot — Architecture Handover

Generated: 2026-08-08T15:58:47.778751+00:00
Basis: current working tree, including uncommitted implementation. Secret values are omitted.

## 1. Executive Summary

The active product is a Vite/React single-page application backed by `backend/app/main.py`, a FastAPI service using SQLAlchemy and PostgreSQL. Cognito access tokens protect nearly every product endpoint. Chat creates a durable `RuntimeExecution`, selects a published managed agent when an explicit ID or heuristic match is available, otherwise falls back to `chat_service`, and streams append-only `RuntimeExecutionEvent` records over authenticated fetch-based SSE.

The repository has broad implemented management surfaces for agents, tools, native tools, MCP, tool discovery/governance, workflows, actions, knowledge-source metadata, audit, and dashboard metrics. Completeness is uneven. Agent management/execution, providers, tool SDK, MCP, runtime events, audit, and metrics have substantial backend implementations. Planner/agent selection remain heuristic; actions have split models/executors; governance has multiple parallel continuation/approval paths; knowledge is not full RAG. Duplicate legacy roots (`src/`, `backend/app/api/main.py`, `backend/backend-deploy/`) are not the active application.

Status vocabulary: **Implemented** = wired active path; **Partial** = real code with missing/unified behavior; **Placeholder** = interface/UI/config without complete capability; **Legacy/dead** = duplicate or not included by active entrypoint.

## 2. Repository Structure

| Area | Actual contents | Status |
|---|---|---|
| `frontend/` | Active React/Vite app, router, layouts, pages, hooks, services, stores, tests | Implemented |
| `backend/app/` | Active FastAPI app, APIs, services, runtime, agents, providers, tools, governance, persistence | Implemented |
| `backend/alembic/` | PostgreSQL schema history through runtime-agent linkage | Implemented |
| `backend/tests/` | Unit/API/migration/security/provider/runtime/tool/MCP tests | Implemented |
| `observability/`, `prometheus/`, `grafana/`, `ecs/` | Local monitoring stack and task definitions | Implemented/configuration |
| `.github/workflows/`, `amplify.yml`, Docker/Procfile | CI, frontend build, backend container/process definitions | Partial deployment definition |
| root `src/` | Older duplicate chat frontend, not used by `frontend/package.json` | Legacy/dead |
| `backend/backend-deploy/`, `backend/app/api/main.py` | Reduced/alternate backend copies, not the documented uvicorn entry | Legacy/dead |

Inventory counts (excluding dependencies/build/cache): 196 frontend source files, 319 backend Python files, 177 API operations, 39 mapped tables.

## 3. Frontend Architecture

`frontend/src/main.jsx` mounts the app, Amplify configuration, global CSS and `QueryProvider`. `frontend/src/App.jsx` handles authentication and renders the `RouterProvider`. `app/router.jsx` lazy-loads pages beneath `EnterpriseLayout`; `Sidebar` supplies product navigation. React Query owns server cache; page-local hooks/state manage UI; runtime events use a reducer. No separate global Redux store exists; Zustand-style files exist for chat/conversation/UI but the active Chat page primarily uses hooks and reducer state.

Major pages and wiring:

| Page | Component | Backend/API | Status |
|---|---|---|---|
| Dashboard | `pages/dashboard/DashboardPage.jsx` | `/api/dashboard/*` | Implemented |
| Chat | `pages/ChatPage.jsx` + chat components | conversations, `/api/chat/start`, `/api/runtime/*` | Implemented, runtime details partial |
| Workflows | `pages/workflows/*` | `/api/workflows`, `/api/workflows/run` | Implemented |
| Agents | `pages/agents/*`, builder/test console | `/api/v1/agents/*` | Implemented |
| Actions | `pages/actions/ActionsPage.jsx` | `/api/actions*` | Partial split runtime |
| Tool Catalog / Integrations / Executions | `pages/tools/*` | `/api/v1/tools*`, integrations, executions | Implemented |
| Native Tools | `pages/native/*` | `/api/v1/native-tools`, files/connections/notifications | Implemented |
| MCP Servers | `pages/mcp/*` | `/api/v1/mcp/*` | Implemented/configuration dependent |
| Discovery / Marketplace / Governance / Analytics | `pages/discovery/*` via `AdminPages.jsx` | `/api/v1/tool-*` | Implemented |
| Knowledge | `pages/knowledge/KnowledgePage.jsx` | `/api/knowledge` | Partial: metadata CRUD only |
| Audit | `pages/audit/AuditPage.jsx` | `/api/audit*` | Implemented |
| Settings | `pages/settings/SettingsPage.jsx` | mostly UI/config view | Partial |

Authentication uses Amplify/Cognito; API services call `getAccessToken()` and send Bearer tokens. `runtime.service.ts` deliberately uses `fetch` rather than `EventSource` so the Authorization header is preserved. Theme is a dark enterprise design in `index.css`, `discovery.css`, and layout/component utility classes.

## 4. Backend Architecture

`backend/app/main.py` is the active entry. Lifespan validates the environment, optionally creates development schema, checks DB connectivity/migration head, optionally syncs/indexes tools, loads approved MCP tools, and registers DB metrics. Middleware: CORS, optional TrustedHost, request logging, security headers. Health/readiness/metrics endpoints and a Mangum Lambda handler are present.

The backend is layered but not strictly isolated: routers frequently query SQLAlchemy directly; application services cover conversations/runtime/agents; reusable legacy workflow runtime classes coexist with the chat-specific `RuntimeExecutionService`; tools and MCP use registries plus persisted catalogs.

## 5. API Catalog

All product routes below were extracted from decorators. `not statically evident` means the handler delegates or uses repository helpers; it does not mean no persistence.

| Method | Path | Handler / router | Wiring | Auth | Request model/args | Response | Service | Direct table classes |
|---|---|---|---|---|---|---|---|---|
| GET | `/` | `root` / `backend/app/main.py` | Active | None | — | — | inline router logic | not statically evident |
| GET | `/api/actions` | `list_actions` / `backend/app/api/management.py` | Active | Bearer/Cognito | — | — | inline router logic | Action |
| POST | `/api/actions` | `create_action` / `backend/app/api/management.py` | Active | Bearer/Cognito | payload: ActionPayload | — | inline router logic | not statically evident |
| PATCH | `/api/actions/{action_id}` | `update_action` / `backend/app/api/management.py` | Active | Bearer/Cognito | action_id: int, payload: dict | — | inline router logic | Action |
| POST | `/api/actions/{action_id}/execute` | `execute_action` / `backend/app/api/management.py` | Active | Bearer/Cognito | action_id: int | — | inline router logic | Action |
| GET | `/api/agents` | `list_agents` / `backend/app/api/management.py` | Active | Bearer/Cognito | — | — | agent_application_service | Agent, RuntimeExecution |
| POST | `/api/agents` | `create_agent` / `backend/app/api/management.py` | Active | Bearer/Cognito | payload: AgentPayload | — | agent_application_service | not statically evident |
| GET | `/api/agents/status` | `operations_agent_status` / `backend/app/api/operations.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| DELETE | `/api/agents/{agent_id}` | `delete_agent` / `backend/app/api/management.py` | Active | Bearer/Cognito | agent_id: int | — | inline router logic | not statically evident |
| GET | `/api/agents/{agent_id}` | `get_agent` / `backend/app/api/management.py` | Active | Bearer/Cognito | agent_id: int | — | agent_application_service | Agent, RuntimeExecution |
| PATCH | `/api/agents/{agent_id}` | `update_agent` / `backend/app/api/management.py` | Active | Bearer/Cognito | agent_id: int, payload: AgentPatch | — | agent_application_service | Agent |
| GET | `/api/agents/{agent_id}/executions` | `get_agent_executions` / `backend/app/api/management.py` | Active | Bearer/Cognito | agent_id: int | — | agent_application_service | Agent, RuntimeExecution |
| GET | `/api/audit` | `list_audit_logs` / `backend/app/api/management.py` | Active | Bearer/Cognito | action: str / None, agent: str / None, date: str, search: str / None | — | inline router logic | RuntimeExecution |
| GET | `/api/audit/runtime-executions` | `list_runtime_executions` / `backend/app/api/audit.py` | Active | Bearer/Cognito | — | — | inline router logic | RuntimeExecution |
| POST | `/api/chat/start` | `start_runtime_execution` / `backend/app/api/chat.py` | Active | Bearer/Cognito | — | RuntimeStartResponse | conversation_service, runtime_execution_service | not statically evident |
| GET | `/api/conversations` | `get_conversations` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | — | — | inline router logic | not statically evident |
| POST | `/api/conversations` | `create_conversation` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | — | — | inline router logic | not statically evident |
| POST | `/api/conversations/message` | `send_message` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | — | ConversationResponse | inline router logic | not statically evident |
| DELETE | `/api/conversations/{conversation_id}` | `delete_conversation` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | conversation_id: str | — | inline router logic | not statically evident |
| PATCH | `/api/conversations/{conversation_id}` | `rename_conversation` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | conversation_id: str | — | inline router logic | not statically evident |
| GET | `/api/conversations/{conversation_id}/messages` | `get_messages` / `backend/app/api/routers/conversations.py` | Legacy / not included | None | conversation_id: str | — | inline router logic | not statically evident |
| GET | `/api/dashboard/agents/status` | `agent_status` / `backend/app/api/routers/dashboard.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/dashboard/executions/trends` | `execution_trends` / `backend/app/api/routers/dashboard.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/dashboard/metrics` | `dashboard_metrics` / `backend/app/api/routers/dashboard.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/dashboard/recent-executions` | `recent_executions` / `backend/app/api/routers/dashboard.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/dashboard/workflow-distribution` | `workflow_distribution` / `backend/app/api/routers/dashboard.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/executions/recent` | `operations_recent_executions` / `backend/app/api/operations.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/executions/{execution_id}/events` | `execution_events` / `backend/app/api/management.py` | Active | Bearer/Cognito | execution_id: UUID | — | inline router logic | not statically evident |
| GET | `/api/knowledge` | `list_knowledge` / `backend/app/api/management.py` | Active | Bearer/Cognito | search: str / None | — | inline router logic | KnowledgeSource |
| POST | `/api/knowledge` | `create_knowledge` / `backend/app/api/management.py` | Active | Bearer/Cognito | payload: KnowledgePayload | — | inline router logic | not statically evident |
| DELETE | `/api/knowledge/{source_id}` | `delete_knowledge` / `backend/app/api/management.py` | Active | Bearer/Cognito | source_id: int | — | inline router logic | KnowledgeSource |
| GET | `/api/runtime` | `get_conversation_runtime` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | conversation_id: UUID | — | inline router logic | RuntimeExecution |
| POST | `/api/runtime/cancel/{execution_id}` | `cancel_runtime_execution` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID | — | runtime_execution_service | not statically evident |
| GET | `/api/runtime/events/{execution_id}` | `runtime_events_stream` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID | — | runtime_execution_service | not statically evident |
| GET | `/api/runtime/{execution_id}` | `get_runtime_execution` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID | — | runtime_execution_service | not statically evident |
| POST | `/api/runtime/{execution_id}/approve` | `approve_runtime_execution` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID, payload: ContinueRequest | — | runtime_execution_service | not statically evident |
| POST | `/api/runtime/{execution_id}/continue` | `continue_runtime_execution` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID, payload: ContinueRequest | — | runtime_execution_service | not statically evident |
| POST | `/api/runtime/{execution_id}/deny` | `deny_runtime_execution` / `backend/app/api/runtime.py` | Active | Bearer/Cognito | execution_id: UUID, payload: ContinueRequest | — | runtime_execution_service | not statically evident |
| POST | `/api/v1/agent-executions/{execution_id}/approve` | `approve` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str, payload: ResumePayload | — | inline router logic | not statically evident |
| POST | `/api/v1/agent-executions/{execution_id}/clarify` | `clarify` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str, payload: ResumePayload | — | inline router logic | not statically evident |
| GET | `/api/v1/agent-executions/{execution_id}/continuation` | `get_continuation` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str | — | agent_execution_service | not statically evident |
| POST | `/api/v1/agent-executions/{execution_id}/deny` | `deny` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str, payload: ResumePayload | — | inline router logic | not statically evident |
| POST | `/api/v1/agent-executions/{execution_id}/input` | `submit_input` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str, payload: ResumePayload | — | inline router logic | not statically evident |
| POST | `/api/v1/agent-executions/{execution_id}/resume` | `resume_generic` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | execution_id: str, payload: ResumePayload | — | agent_execution_service | not statically evident |
| GET | `/api/v1/agents` | `list_agents` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | search: str / None, status: Literal['draft', 'published', 'enabled', 'disabled', 'archived', 'error'] / None, owner: str / None, model: str / None, environment: str / None, include_archived: bool, sort: Literal['name', 'updated_at', 'lifecycle', 'owner'], direction: Literal['asc', 'desc'], page: int, page_size: int | — | agent_application_service | AgentKnowledgeAssignment, AgentToolAssignment |
| POST | `/api/v1/agents` | `create_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | payload: AgentCreate | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/capabilities/options` | `capability_options` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | — | — | agent_application_service | KnowledgeSource, ToolDefinition |
| GET | `/api/v1/agents/{agent_id}` | `get_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str | — | agent_application_service | not statically evident |
| PATCH | `/api/v1/agents/{agent_id}` | `update_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: AgentUpdate, if_match: int | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/access` | `get_access` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str | — | inline router logic | not statically evident |
| PUT | `/api/v1/agents/{agent_id}/access` | `put_access` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: AccessAssignments | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/activity` | `get_activity` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, event_type: str / None, page: int, page_size: int | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/analytics` | `agent_analytics` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, started_from: datetime / None, started_to: datetime / None, environment: Literal['development', 'staging', 'production'] / None, mode: Literal['test', 'production'] / None, tool: str / None, status: str / None, version: int / None | — | inline router logic | Agent, AgentContinuation, AgentExecution, ToolExecution |
| POST | `/api/v1/agents/{agent_id}/archive` | `archive_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: LifecyclePayload, if_match: int | — | inline router logic | not statically evident |
| POST | `/api/v1/agents/{agent_id}/disable` | `disable_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: LifecyclePayload, if_match: int | — | inline router logic | not statically evident |
| GET | `/api/v1/agents/{agent_id}/effective-access` | `get_effective_access` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, action: Literal['view', 'edit', 'publish', 'execute', 'manage_tools', 'manage_knowledge', 'manage_access', 'view_executions', 'view_analytics'] | — | agent_application_service | not statically evident |
| POST | `/api/v1/agents/{agent_id}/enable` | `enable_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: LifecyclePayload, if_match: int | — | inline router logic | not statically evident |
| POST | `/api/v1/agents/{agent_id}/execute` | `execute_agent` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, payload: ExecutePayload | — | agent_execution_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/executions` | `list_agent_executions` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, status: str / None, mode: str / None, actor: str / None, started_from: datetime / None, started_to: datetime / None, tool: str / None, version: int / None, sort: Literal['started_at', 'duration_ms', 'status', 'agent_version'], direction: Literal['asc', 'desc'], page: int, page_size: int | — | agent_execution_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/executions/{execution_id}` | `get_agent_execution` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, execution_id: str | — | agent_execution_service | AgentContinuation, ToolDiscoveryEvent, ToolExecution |
| POST | `/api/v1/agents/{agent_id}/executions/{execution_id}/cancel` | `cancel_agent_execution` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, execution_id: str | — | agent_execution_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/knowledge` | `get_knowledge` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str | — | inline router logic | not statically evident |
| PUT | `/api/v1/agents/{agent_id}/knowledge` | `put_knowledge` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: KnowledgeAssignments | — | agent_application_service | not statically evident |
| POST | `/api/v1/agents/{agent_id}/publish` | `publish_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: LifecyclePayload, if_match: int | — | agent_application_service | not statically evident |
| POST | `/api/v1/agents/{agent_id}/restore` | `restore_agent` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: LifecyclePayload, if_match: int | — | inline router logic | not statically evident |
| POST | `/api/v1/agents/{agent_id}/test` | `test_agent` / `backend/app/api/agent_executions.py` | Active | Bearer/Cognito | agent_id: str, payload: ExecutePayload | — | agent_execution_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/tools` | `get_tools` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str | — | inline router logic | not statically evident |
| PUT | `/api/v1/agents/{agent_id}/tools` | `put_tools` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, payload: ToolAssignments | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/versions` | `list_versions` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str | — | agent_application_service | not statically evident |
| GET | `/api/v1/agents/{agent_id}/versions/{version}` | `get_version` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, version: int | — | agent_application_service | not statically evident |
| DELETE | `/api/v1/agents/{agent_id}/{kind}/{assignment_id}` | `delete_assignment` / `backend/app/api/agents_v1.py` | Active | Bearer/Cognito | agent_id: str, kind: Literal['tools', 'knowledge', 'access'], assignment_id: str | — | agent_application_service | not statically evident |
| GET | `/api/v1/api-connections` | `api_connections` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| POST | `/api/v1/api-connections` | `create_api_connection` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | payload: ConnectionBody | — | inline router logic | not statically evident |
| POST | `/api/v1/api-connections/{connection_id}/request` | `api_request` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | connection_id: str, payload: dict | — | inline router logic | not statically evident |
| GET | `/api/v1/approvals` | `list_approvals` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | status: str / None, page: int, page_size: int | — | inline router logic | ApprovalRequest |
| GET | `/api/v1/approvals/{request_id}` | `get_approval` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | request_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/approvals/{request_id}/approve` | `approve` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | request_id: str, payload: DecisionPayload | — | inline router logic | not statically evident |
| POST | `/api/v1/approvals/{request_id}/deny` | `deny` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | request_id: str, payload: DecisionPayload | — | inline router logic | not statically evident |
| POST | `/api/v1/approvals/{request_id}/resume` | `resume` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | request_id: str, payload: ResumePayload | — | inline router logic | not statically evident |
| POST | `/api/v1/approvals/{request_id}/revoke` | `revoke` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | request_id: str, payload: DecisionPayload | — | inline router logic | not statically evident |
| GET | `/api/v1/clarifications/{clarification_id}` | `get_clarification` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | clarification_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/clarifications/{clarification_id}/cancel` | `cancel_clarification` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | clarification_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/clarifications/{clarification_id}/resume` | `resume_clarification` / `backend/app/api/governance_workflows.py` | Active | Bearer/Cognito | clarification_id: str, payload: ClarificationResumePayload | — | inline router logic | not statically evident |
| GET | `/api/v1/database-connections` | `database_connections` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| POST | `/api/v1/database-connections` | `create_database_connection` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | payload: ConnectionBody | — | inline router logic | not statically evident |
| POST | `/api/v1/database/query/execute` | `database_execute` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | payload: dict | — | inline router logic | not statically evident |
| GET | `/api/v1/files` | `list_files` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | search: str / None, status: str / None, page: int, page_size: int | — | inline router logic | NativeFile |
| POST | `/api/v1/files` | `upload_file` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | file: UploadFile | — | inline router logic | not statically evident |
| POST | `/api/v1/files/search` | `search_files` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | payload: dict | — | inline router logic | not statically evident |
| GET | `/api/v1/files/{file_id}` | `get_file` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | file_id: str | — | inline router logic | NativeFile |
| GET | `/api/v1/files/{file_id}/content` | `file_content` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | file_id: str | — | inline router logic | NativeFile, NativeFileContent |
| POST | `/api/v1/files/{file_id}/extract` | `extract` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | file_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/files/{file_id}/summarize` | `summarize` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | file_id: str, payload: dict / None | — | inline router logic | not statically evident |
| GET | `/api/v1/integrations` | `integrations` / `backend/app/api/tools.py` | Active | Bearer/Cognito | — | — | inline router logic | IntegrationConfiguration |
| PUT | `/api/v1/integrations/{provider}` | `upsert_integration` / `backend/app/api/tools.py` | Active | Bearer/Cognito | provider: str, payload: IntegrationPayload | — | inline router logic | IntegrationConfiguration |
| POST | `/api/v1/integrations/{provider}/verify` | `verify_integration` / `backend/app/api/tools.py` | Active | Bearer/Cognito | provider: str | — | inline router logic | IntegrationConfiguration |
| GET | `/api/v1/mcp/servers` | `list_servers` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | search: str / None, enabled: bool / None, health: str / None, page: int, page_size: int | — | inline router logic | MCPServer |
| POST | `/api/v1/mcp/servers` | `create_server` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | payload: ServerPayload | — | inline router logic | MCPServer |
| DELETE | `/api/v1/mcp/servers/{server_id}` | `delete_server` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | MCPCapability |
| GET | `/api/v1/mcp/servers/{server_id}` | `get_server` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | MCPCapability |
| PATCH | `/api/v1/mcp/servers/{server_id}` | `update_server` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, payload: ServerUpdate | — | inline router logic | not statically evident |
| GET | `/api/v1/mcp/servers/{server_id}/capabilities` | `capabilities` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, type: str / None | — | inline router logic | MCPCapability |
| PATCH | `/api/v1/mcp/servers/{server_id}/capabilities/{capability_id}` | `update_capability` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, capability_id: str, payload: CapabilityUpdate | — | inline router logic | MCPCapability |
| GET | `/api/v1/mcp/servers/{server_id}/executions` | `executions` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | MCPCapability, ToolExecution |
| GET | `/api/v1/mcp/servers/{server_id}/oauth/callback` | `oauth_callback` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, state: str, code: str | — | inline router logic | not statically evident |
| POST | `/api/v1/mcp/servers/{server_id}/oauth/start` | `oauth_start` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/mcp/servers/{server_id}/prompts/{name}` | `prompt_get` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, name: str, payload: PromptPayload | — | inline router logic | not statically evident |
| POST | `/api/v1/mcp/servers/{server_id}/resources/read` | `resource_read` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, payload: ResourcePayload | — | inline router logic | not statically evident |
| POST | `/api/v1/mcp/servers/{server_id}/sync` | `synchronize` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, correlation_id: str / None | — | inline router logic | not statically evident |
| GET | `/api/v1/mcp/servers/{server_id}/sync-runs` | `sync_runs` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | MCPSyncRun |
| POST | `/api/v1/mcp/servers/{server_id}/test` | `test_connection` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/mcp/servers/{server_id}/tools/{capability_id}/execute` | `execute_tool` / `backend/app/api/mcp.py` | Active | Bearer/Cognito | server_id: str, capability_id: str, payload: ExecutePayload, idempotency_key: str / None, correlation_id: str / None | — | inline router logic | MCPCapability |
| GET | `/api/v1/native-tools` | `list_native_tools` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | search: str / None | — | inline router logic | not statically evident |
| GET | `/api/v1/native-tools/{name}` | `get_native_tool` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | name: str | — | inline router logic | not statically evident |
| POST | `/api/v1/native-tools/{name}/execute` | `execute_native` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | name: str, payload: ExecuteBody | — | inline router logic | not statically evident |
| GET | `/api/v1/notifications` | `notifications` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | — | — | inline router logic | NativeNotification |
| POST | `/api/v1/notifications/{channel}` | `create_notification` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | channel: str, payload: dict | — | inline router logic | not statically evident |
| POST | `/api/v1/notifications/{notification_id}/approve` | `approve_notification` / `backend/app/api/native_tools.py` | Active | Bearer/Cognito | notification_id: str | — | inline router logic | NativeNotification |
| GET | `/api/v1/tool-analytics/cost` | `cost` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-analytics/discovery-quality` | `quality` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | ToolDiscoveryFeedback |
| GET | `/api/v1/tool-analytics/failures` | `failures` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-analytics/outcomes` | `outcomes` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-analytics/performance` | `performance` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-analytics/recommendations` | `recommendations` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-analytics/summary` | `analytics_summary` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | ToolDiscoveryEvent, ToolExecution |
| GET | `/api/v1/tool-analytics/usage` | `usage` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | days: int | — | inline router logic | not statically evident |
| POST | `/api/v1/tool-discovery/index/rebuild` | `rebuild` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | dry_run: bool, batch_size: int | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-discovery/index/status` | `index_status` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | — | — | inline router logic | ToolSearchIndex |
| POST | `/api/v1/tool-discovery/search` | `discover` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | payload: DiscoveryRequest | — | inline router logic | not statically evident |
| POST | `/api/v1/tool-discovery/simulate` | `simulate` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | payload: DiscoveryRequest | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-discovery/{discovery_id}` | `discovery_detail` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | discovery_id: str | — | inline router logic | ToolCandidateDecision, ToolDiscoveryEvent |
| POST | `/api/v1/tool-discovery/{discovery_id}/feedback` | `feedback` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | discovery_id: str, payload: FeedbackPayload | — | inline router logic | ToolDiscoveryEvent |
| GET | `/api/v1/tool-executions` | `history` / `backend/app/api/tools.py` | Active | Bearer/Cognito | tool: str / None, status_filter: str / None, page: int, page_size: int | — | inline router logic | ToolExecution |
| GET | `/api/v1/tool-executions/{execution_id}` | `execution_detail` / `backend/app/api/tools.py` | Active | Bearer/Cognito | execution_id: str | — | inline router logic | ToolExecution |
| POST | `/api/v1/tool-governance/evaluate` | `evaluate_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | payload: DiscoveryRequest | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-governance/policies` | `policies` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | — | — | inline router logic | ToolGovernancePolicy |
| POST | `/api/v1/tool-governance/policies` | `create_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | payload: PolicyPayload | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-governance/policies/{policy_id}` | `get_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | policy_id: str | — | inline router logic | ToolGovernancePolicy |
| PATCH | `/api/v1/tool-governance/policies/{policy_id}` | `update_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | policy_id: str, payload: PolicyPayload | — | inline router logic | ToolGovernancePolicy |
| POST | `/api/v1/tool-governance/policies/{policy_id}/publish` | `publish_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | policy_id: str | — | inline router logic | ToolGovernancePolicy |
| POST | `/api/v1/tool-governance/policies/{policy_id}/test` | `test_policy` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | policy_id: str, payload: DiscoveryRequest | — | inline router logic | not statically evident |
| GET | `/api/v1/tool-marketplace` | `marketplace` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | search: str / None, source: str / None, status: str / None, category: str / None, risk: str / None, page: int, page_size: int | — | inline router logic | ToolMarketplaceProfile |
| GET | `/api/v1/tool-marketplace/{tool_id}` | `marketplace_detail` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str | — | inline router logic | ToolMarketplaceProfile |
| PATCH | `/api/v1/tool-marketplace/{tool_id}` | `marketplace_update` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str, payload: MarketplacePatch | — | inline router logic | ToolMarketplaceProfile |
| PUT | `/api/v1/tool-marketplace/{tool_id}/assignments` | `assignments` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str, payload: AssignmentPayload | — | inline router logic | ToolAssignment, ToolMarketplaceProfile |
| POST | `/api/v1/tool-marketplace/{tool_id}/disable` | `marketplace_disable` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str | — | inline router logic | not statically evident |
| POST | `/api/v1/tool-marketplace/{tool_id}/enable` | `marketplace_enable` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str | — | inline router logic | not statically evident |
| PUT | `/api/v1/tool-marketplace/{tool_id}/governance` | `governance` / `backend/app/api/tool_discovery.py` | Active | Bearer/Cognito | tool_id: str, payload: MarketplacePatch | — | inline router logic | not statically evident |
| GET | `/api/v1/tools` | `list_tools` / `backend/app/api/tools.py` | Active | Bearer/Cognito | search: str / None, category: str / None, provider: str / None, tag: str / None, enabled: bool / None, risk_level: str / None, page: int, page_size: int, sort: str | — | inline router logic | not statically evident |
| GET | `/api/v1/tools/categories` | `categories` / `backend/app/api/tools.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/v1/tools/providers` | `providers` / `backend/app/api/tools.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| GET | `/api/v1/tools/{name}` | `detail` / `backend/app/api/tools.py` | Active | Bearer/Cognito | name: str, version: str / None | — | inline router logic | ToolExecution |
| POST | `/api/v1/tools/{name}/execute` | `execute` / `backend/app/api/tools.py` | Active | Bearer/Cognito | name: str, payload: ExecutePayload, idempotency_key: str / None, x_correlation_id: str / None, approval_request_id: str / None, approval_resume_token: str / None | — | inline router logic | not statically evident |
| GET | `/api/v1/tools/{name}/versions` | `versions` / `backend/app/api/tools.py` | Active | Bearer/Cognito | name: str | — | inline router logic | not statically evident |
| PATCH | `/api/v1/tools/{name}/{version}/enabled` | `enable_tool` / `backend/app/api/tools.py` | Active | Bearer/Cognito | name: str, version: str, enabled: bool | — | inline router logic | not statically evident |
| GET | `/api/workflows` | `list_managed_workflows` / `backend/app/api/management.py` | Active | Bearer/Cognito | — | — | inline router logic | Workflow |
| POST | `/api/workflows` | `create_managed_workflow` / `backend/app/api/management.py` | Active | Bearer/Cognito | payload: WorkflowPayload | — | inline router logic | not statically evident |
| DELETE | `/api/workflows/{workflow_id}` | `delete_managed_workflow` / `backend/app/api/management.py` | Active | Bearer/Cognito | workflow_id: int | — | inline router logic | Workflow |
| GET | `/api/workflows/{workflow_id}` | `get_managed_workflow` / `backend/app/api/management.py` | Active | Bearer/Cognito | workflow_id: int | — | inline router logic | Workflow |
| PUT | `/api/workflows/{workflow_id}` | `update_managed_workflow` / `backend/app/api/management.py` | Active | Bearer/Cognito | workflow_id: int, payload: WorkflowPayload | — | inline router logic | Workflow |
| POST | `/api/workflows/{workflow_id}/execute` | `execute_managed_workflow` / `backend/app/api/management.py` | Active | Bearer/Cognito | workflow_id: int | — | inline router logic | Workflow |
| GET | `/auth/me` | `me` / `backend/app/api/auth.py` | Active | Bearer/Cognito | — | — | inline router logic | not statically evident |
| POST | `/chat` | `chat` / `backend/app/api/chat.py` | Active | Bearer/Cognito | — | ChatResponse | chat_service | not statically evident |
| POST | `/chat/stream` | `stream_chat` / `backend/app/api/chat.py` | Active | Bearer/Cognito | payload: ChatRequest | — | chat_service | not statically evident |
| GET | `/conversations` | `get_conversations` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | — | list[ConversationResponse] | conversation_service | not statically evident |
| POST | `/conversations` | `create_conversation` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | — | ConversationResponse | conversation_service | not statically evident |
| DELETE | `/conversations/{conversation_id}` | `delete_conversation` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | conversation_id: UUID | — | conversation_service | not statically evident |
| GET | `/conversations/{conversation_id}` | `get_conversation` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | conversation_id: UUID | ConversationResponse | conversation_service | not statically evident |
| PATCH | `/conversations/{conversation_id}` | `update_conversation` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | conversation_id: UUID | ConversationResponse | conversation_service | not statically evident |
| GET | `/conversations/{conversation_id}/messages` | `get_messages` / `backend/app/api/conversation.py` | Active | Bearer/Cognito | conversation_id: UUID | — | conversation_service | not statically evident |
| GET | `/health` | `health` / `backend/app/main.py` | Active | None | — | — | inline router logic | not statically evident |
| GET | `/health/details` | `health_details` / `backend/app/main.py` | Active | None | — | — | inline router logic | not statically evident |
| GET | `/metrics` | `metrics` / `backend/app/main.py` | Active | None | — | — | inline router logic | not statically evident |
| GET | `/ready` | `readiness` / `backend/app/main.py` | Active | None | — | — | inline router logic | not statically evident |
| GET | `/workflows` | `list_workflows` / `backend/app/api/routers/workflows.py` | Active | None | — | — | inline router logic | not statically evident |
| POST | `/workflows/run` | `run_workflow` / `backend/app/api/routers/workflows.py` | Active | None | goal: str / None | — | inline router logic | not statically evident |
| GET | `/workflows/{workflow_id}` | `get_workflow` / `backend/app/api/routers/workflows.py` | Active | None | workflow_id: int | — | inline router logic | not statically evident |


## 6. Chat Runtime

1. `ChatPage` loads/creates a conversation and calls `useChat.handleStream`.
2. Frontend posts `/api/chat/start` with `conversation_id`, message and optional agent/provider/model/workspace.
3. API verifies conversation ownership and derives permissions/tenant from Cognito claims.
4. `RuntimeExecutionService.start` selects an enabled published tenant agent (explicit match or heuristic confidence), resolves provider/model, persists `RuntimeExecution` and user message, writes audit, and launches an asyncio task.
5. Managed selection calls `AgentExecutionService` with `runtime_execution_id`; otherwise the default chat/provider path executes. Tool schema can produce required-input fields; approval gates produce durable continuations.
6. Every published event updates the runtime summary, appends `RuntimeExecutionEvent`, and enters an in-process tracker. SSE replays persisted events when needed, then tails the tracker.
7. The reducer merges steps/tools/actions/logs/metrics and renders `RuntimeExecutionCard`/`ExecutionInspector` plus continuation UI.

`RuntimeExecution.id` is the UI/SSE execution ID. `workflow_id` is a runtime correlation ID. `conversation_id` links messages/context. `AgentExecution.id` is distinct and is linked through `AgentExecution.runtime_execution_id` (string without a declared FK).

## 7. Runtime State Machine

Declared runtime transitions: `PENDING → RUNNING|CANCELLED`; `RUNNING → WAITING_FOR_INPUT|WAITING_FOR_APPROVAL|COMPLETED|FAILED|CANCELLED|TIMED_OUT`; waiting states may resume to `RUNNING` or terminate. All requested states exist in service logic. Agent execution additionally supports `waiting_for_clarification`, `expired`, queued/running/succeeded/failed/cancelled/timed_out. State naming/casing differs between the two execution systems.

## 8. Agent Architecture

Managed agents are tenant-scoped rows with lifecycle/health, mutable draft configuration and immutable published `AgentVersion` snapshots. Publishing, enabling, disabling, archiving/restoring, assignments, version history, activity, analytics and test execution have APIs/UI. `AgentApplicationService` resolves identity/access and published runtime configuration. `AgentExecutionService` is the canonical persisted-agent entry point, records model/planner/tool/knowledge metadata and supports durable continuations with hashed one-time resume tokens.

Separately, `runtime/agent_registry.py`, `agents/default_agent.py`, and older agent models support the reusable workflow runtime. This in-memory/default agent mechanism is real but distinct from managed database agents.

## 9. Planner

`DefaultPlanner` implements the planner contract but still defaults to `required_capabilities = ["general-execution"]`, creates one “Echo Goal” task, and only replaces the capability when tool discovery selects a tool. Chat runtime also performs inline intent classification, agent ranking, tool matching and plan event construction. Managed agent execution accepts planner names `default`, `react`, and `sequential`, but the provider call path is not a full autonomous ReAct engine. Status: **partial/hardcoded**.

## 10. AI Provider Architecture

`AIProviderFactory` caches provider objects by provider/model. OpenAI uses the Responses API (`responses.create`, including stream events); Bedrock uses boto3 Bedrock Runtime `converse`/`converse_stream`, with regional Nova inference-profile resolution. Adapters translate provider-neutral messages. Both collect latency/token/error metrics and map provider failures to safe domain errors. Provider-level streaming exists; the current durable chat path primarily emits orchestration/result events rather than token deltas.

## 11. Tool Architecture

`ToolRegistry` is populated with built-in plus native tools at import, optionally synced to `tool_definitions` and indexed at startup, and augmented by approved MCP tools. `ToolDiscoveryEngine` filters by identity, permissions, environment, health and governance, then ranks indexed candidates. `ToolExecutor` validates schema, permissions, enablement and policy again before execution and persists execution/audit/metrics.

Actually implemented families include ServiceNow incident/change/asset reads; bounded local file operations; Azure Blob reads/listing; Azure Key Vault reads; report-generation support; native file upload/extract/search/summarize; read-only database query; governed REST request; notification/email approval flow; and approved MCP remote tools. Most external adapters require environment configuration and surface `not_configured` until present.

## 12. Action Architecture

There are two action representations: a simple `actions` management table/API/UI and contract-based in-memory actions (`ActionRegistry`, example deployment-report action, `ActionExecutor`, permission/audit helper models). The runtime registers the report action directly. Retry/risk/approval/audit abstractions exist, but the DB-managed action rows are not uniformly executable through the same governed registry. Status: **partially implemented / not unified**.

## 13. MCP Architecture

MCP server configuration, health testing, sync runs, tool/resource/prompt operations, OAuth start/callback, schema fingerprinting, capability approval and tool registry integration are implemented. Supported transports are streamable HTTP and legacy SSE. SSRF/TLS/host/size controls and environment-secret references are present. A configured server is not active until enabled; a remote tool additionally must be approved, enabled, present and not awaiting schema review.

## 14. Discovery Architecture

Discovery indexes registered tools, parses intent, performs authorization/governance filters, ranks candidates, returns selected/clarification/no-match outcomes, and persists discovery events, candidate decisions and feedback. Marketplace and analytics APIs consume these records. It feeds tool selection. It does **not** currently discover knowledge documents, synthesize actions, or create agents.

## 15. Knowledge Architecture

The system persists knowledge-source metadata and agent assignments. Managed agent execution loads authorized source records and can add citation/source metadata to context and runtime events. No document/chunk model, ingestion worker, embedding persistence, vector index, or semantic retriever is implemented. The “Upload source” UI creates metadata; it does not upload file content. Status: **partial; not full RAG**.

## 16. Governance

Tool governance policies support draft/version/publish/test/evaluate and decisions allow, approval-required, deny. Execution rechecks authorization and policy. Agent access assignments grant view/edit/execute/test and identity groups/roles/scopes contribute platform permissions. Durable approval/clarification APIs and both runtime/agent continuation tables exist. Because standalone governance workflows, runtime continuations, agent continuations, native notification approvals, and older approval classes coexist, approval orchestration is **implemented in parts but not one unified state machine**.

## 17. Authentication / Authorization

Cognito access tokens are verified against cached JWKS (RS256, issuer, `token_use=access`, client ID). Claims supply `sub`, `custom:tenant_id`, groups and scopes/permissions. Platform-admin groups add administrative tool permission; agent authorization also evaluates assignments. Most modern queries filter tenant. Risks: legacy workflow/conversation code contains default-tenant paths, authorization is convention/service based rather than database row-level security, and JWKS retrieval is synchronous within token verification. E2E token support is gated to isolated environments.

## 18. Data Architecture

PostgreSQL is the production target; SQLAlchemy/Alembic own schema. UUID/string identity styles and UTC handling vary by generation. Runtime events are append-only with unique `(execution_id, sequence)`, but sequence allocation uses count+1 and can race under concurrent writers. Some conceptual links (`runtime_execution_id`, conversation IDs in agent execution) are strings without declared foreign keys. See `database_schema.md`.

## 19. AWS Architecture

Repository evidence directly supports Cognito, Bedrock Runtime, RDS/PostgreSQL and Secrets Manager. Amplify build configuration exists. FastAPI includes a Mangum handler, but API Gateway/Lambda infrastructure is not defined. Docker/Procfile and ECS Prometheus/Grafana task definitions also exist, producing multiple deployment possibilities. VPC, subnets, security groups, load balancer, ECS application task/service and CloudWatch log wiring are **not defined in repository**.

## 20. Event Streaming

Event types produced include `step`, `completed`, `error`, `required_input`, `approval_required`, `tool_started|completed|failed`, `action_started|completed|failed`, `metric`, `log`, `knowledge_retrieval_completed`, plus heartbeat comments. Runtime workflow bus events are translated into steps. Events are both in-memory and database-persisted. Reconnect retries up to four times; persisted ordered replay occurs when the process tracker lacks events. There is no `Last-Event-ID`/sequence request cursor and no cross-process pub/sub, so horizontal live streaming is a risk.

## 21. Observability

Request logging attaches request IDs and duration; security-sensitive values are sanitized/redacted. Prometheus metrics cover HTTP/provider/token/error/latency, agents, tools/discovery and DB pool/query behavior. `/health`, `/ready`, `/health/details`, `/metrics` exist. Prometheus/Grafana configs and dashboards exist. Persistent audit logs cover runtime/agent/tool/governance operations. A centralized production log backend/alerting/IaC is not defined.

## 22. Configuration

Important settings (values omitted): `APP_ENV`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_INFERENCE_PROFILE_ID`, `BEDROCK_MAX_TOKENS`, `BEDROCK_TEMPERATURE`, `BEDROCK_TOP_P`, `AUTO_AGENT_MIN_CONFIDENCE`, `DATABASE_URL`, `DATABASE_SECRET_ARN`, `DATABASE_HOST/PORT/NAME`, DB pool controls, `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, `RUN_SCHEMA_CREATE`, `SYNC_TOOL_CATALOG_ON_STARTUP`, `ENABLE_API_DOCS`, frontend `VITE_API_URL` and `VITE_COGNITO_*`. Capability adapters additionally consume ServiceNow/Azure/file/native/MCP environment settings. Secret values must remain in secret stores or environment injection.

## 23. Deployment

Frontend: Vite build under `frontend/`, with Amplify config and static security headers. Backend: Dockerfile/Procfile run FastAPI/uvicorn; production startup requires current migrations and secure settings. `docker-compose.yml` and observability compose support local operation. The presence of Mangum and ECS monitoring files does not establish a single production topology. Deployment dependencies include PostgreSQL, Cognito JWKS reachability, configured model provider credentials/IAM, and any selected enterprise adapters.

## 24. Known Technical Debt

- Duplicate frontend/backend roots and overlapping API/service generations.
- Runtime planning/selection logic is spread across `RuntimeExecutionService`, `DefaultPlanner`, workflow runtime and `AgentExecutionService`.
- Runtime and agent statuses/continuations use different casing and models.
- Route handlers frequently contain persistence/business logic.
- String-only conceptual relationships lack foreign keys.
- Event sequence count+1 is not concurrency-safe.
- Provider/model selection behavior differs between managed agent and fallback paths.
- Minified/one-line frontend modules reduce maintainability.

## 25. Partially Implemented Components

Planner/agent selection, action unification, knowledge/RAG, unified governance/approval, multi-process SSE, Settings, AWS infrastructure definition, deployment topology, and some legacy workflow integration.

## 26. Known Broken Flows

- Knowledge “upload” cannot ingest/retrieve document content.
- Live SSE across multiple backend processes has no shared broker.
- Last-event cursor replay is absent and reconnect may duplicate events depending on process state.
- DB-managed arbitrary action execution is not the same path as registered action contracts.
- Selecting configured agent-builder defaults (`provider=configured`, `model=model-a`) can publish unusable runtime model configuration unless replaced with a real provider/model.
- Root legacy `src/` changes do not affect the active `frontend/` build.

## 27. Architecture Risks

Highest risks are execution-path duplication, authorization drift between generations, multi-process event delivery, incomplete RAG expectations, external adapter secret/config sprawl, and deployment ambiguity. The database contains tenant IDs but enforcement relies on application filters. Long-running work uses in-process asyncio tasks and is not durable across process restart.

## 28. Recommended Next Development Steps

1. Make `RuntimeExecutionService` the thin durable shell around one canonical planner/selector and `AgentExecutionService`; define one status/continuation contract.
2. Replace in-process task/tracker fanout with a durable job runner and Redis/Postgres pub-sub or equivalent; add cursor-based SSE replay.
3. Unify DB actions with governed action contracts/executor and approval/audit.
4. Implement real knowledge ingestion/chunking/embedding/vector retrieval, or relabel the UI as source metadata management.
5. Consolidate duplicate roots/entrypoints after proving they are unused.
6. Add explicit infrastructure-as-code and a single documented deployment topology/security boundary.
7. Add database constraints/RLS or a centralized tenant-scoped repository layer.

## 29. Key File Index

| Capability | Frontend | Backend | Persistence | API |
|---|---|---|---|---|
| Chat/runtime | `ChatPage.jsx`, `useChat.js`, `runtime.service.ts`, reducer/cards | `api/chat.py`, `api/runtime.py`, `runtime_execution_service.py` | conversations/messages/runtime executions/events/continuations | `/api/chat/start`, `/api/runtime/*` |
| Agents | agents pages/components/service | `api/agents_v1.py`, `agents/application_service.py`, `agents/execution_service.py` | agents, versions, activity, assignments, executions, continuations | `/api/v1/agents/*` |
| Providers | Chat header selection | `ai/factory.py`, providers/adapters, core clients | execution provider/model/usage fields | through chat/agent execution |
| Tools/discovery | tools/native/discovery pages/services | `api/tools.py`, `api/native_tools.py`, `api/tool_discovery.py`, `tool_sdk/*`, `tool_discovery/*` | tool definitions/executions/index/marketplace/policies/events | `/api/v1/tools*`, `/api/v1/native-*`, `/api/v1/tool-*` |
| Actions | Actions page/service | `api/management.py`, `actions/*`, runtime registration | actions; audit logs | `/api/actions*` |
| MCP | MCP pages/service | `api/mcp.py`, `mcp_integration/*` | MCP servers/capabilities/sync runs | `/api/v1/mcp/*` |
| Knowledge | Knowledge page/service | management API, agent execution retrieval | knowledge_sources, agent_knowledge_assignments | `/api/knowledge*` |
| Governance | Governance page/service, continuation UI | tool governance, governance workflows, approval modules | policies, approval/clarification requests, continuations | `/api/v1/tool-governance/*`, approvals/clarifications |
| Auth/security | `useAuth`, Amplify config, auth services | `auth/*`, middleware, sanitization/headers | claim references, tenant columns | Bearer dependency; `/api/auth/me` |
| Dashboard/ops | Dashboard page/hooks/components | dashboard/operations routers | aggregate runtime/workflow/agent tables | `/api/dashboard/*`, `/api/executions/recent` |
| Audit/metrics | Audit page | audit services/events, metrics/logging | audit_logs | `/api/audit*`, `/metrics` |

## 30. Diagram Index

- `architecture_actions.png` — editable source `architecture_actions.svg`
- `architecture_agents.png` — editable source `architecture_agents.svg`
- `architecture_ai_providers.png` — editable source `architecture_ai_providers.svg`
- `architecture_api.png` — editable source `architecture_api.svg`
- `architecture_aws.png` — editable source `architecture_aws.svg`
- `architecture_backend.png` — editable source `architecture_backend.svg`
- `architecture_chat_runtime.png` — editable source `architecture_chat_runtime.svg`
- `architecture_code_dependencies.png` — editable source `architecture_code_dependencies.svg`
- `architecture_configuration.png` — editable source `architecture_configuration.svg`
- `architecture_database.png` — editable source `architecture_database.svg`
- `architecture_discovery.png` — editable source `architecture_discovery.svg`
- `architecture_frontend.png` — editable source `architecture_frontend.svg`
- `architecture_governance.png` — editable source `architecture_governance.svg`
- `architecture_implementation_status.png` — editable source `architecture_implementation_status.svg`
- `architecture_knowledge.png` — editable source `architecture_knowledge.svg`
- `architecture_master.png` — editable source `architecture_master.svg`
- `architecture_mcp.png` — editable source `architecture_mcp.svg`
- `architecture_observability.png` — editable source `architecture_observability.svg`
- `architecture_planner_agent_selection.png` — editable source `architecture_planner_agent_selection.svg`
- `architecture_security_auth.png` — editable source `architecture_security_auth.svg`
- `architecture_sequence_chat.png` — editable source `architecture_sequence_chat.svg`
- `architecture_sse_events.png` — editable source `architecture_sse_events.svg`
- `architecture_tools.png` — editable source `architecture_tools.svg`


## Current Chat Implementation Status

| Capability | Status | Evidence / limitation |
|---|---|---|
| Conversation persistence/titles | Implemented | Conversation/messages tables and services; title utility/backend updates |
| Agent selector / automatic selection | Partial | Enabled published tenant agents; explicit authorization; heuristic lexical confidence |
| Provider/model resolution | Implemented | request/default/managed-version resolution; paths differ |
| Planner | Partial | inline runtime planning plus hardcoded DefaultPlanner fallback |
| Tool execution | Implemented | discovery, schema, permissions, governance, persisted execution |
| Action execution | Partial | registered report action works; action systems not unified |
| Required-input detection / WAITING_FOR_INPUT | Implemented | selected tool JSON schema → durable continuation |
| Continuation | Implemented | validation, expiry, one-use semantics; parallel runtime/agent models |
| Approval | Partial | durable gates/APIs exist; multiple approval systems |
| SSE | Implemented | authenticated fetch stream, DB append/replay, heartbeat |
| SSE persistence | Implemented | `runtime_execution_events` |
| SSE reconnect | Partial | four retries, no cursor/Last-Event-ID, no shared live broker |
| RuntimeExecution/AgentExecution link | Implemented without FK | `runtime_execution_id` string and migration |
| Bedrock/OpenAI | Implemented | Converse/Responses, streaming/provider metrics |
| Runtime duration/failure | Implemented | duration/error/status fields and terminal events |
| Chat layout/runtime inspector | Implemented | three-pane page and inspector/cards |
| Audit/metrics | Implemented | runtime/agent/tool audit and Prometheus; production sinks undefined |
