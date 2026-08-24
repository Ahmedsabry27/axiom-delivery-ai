# Agents architecture and operations

The canonical Agent aggregate is tenant-scoped in `agents`, with immutable `agent_versions`, relational tool/knowledge/access assignments, durable `agent_executions`, and replay-safe continuations. `AgentApplicationService` owns configuration, legal lifecycle transitions, optimistic locking, authorization, assignment validation, immutable activity, and runtime-cache invalidation. `AgentExecutionService` resolves an enabled Agent and exact published version, invokes Tool Discovery and the existing Tool Executor, restricts retrieval to assigned ready knowledge, and persists safe results and linkage identifiers.

The React administration surface uses `/api/v1/agents`; details tabs are URL-addressable with `?tab=`. Chat and Test Console use the same governed execution and continuation APIs. Test mode does not bypass governance.

Local checks:

```text
cd backend && .venv/bin/alembic upgrade head && .venv/bin/pytest -q
cd frontend && npm test && npm run lint && npm run build
cd frontend && npm run test:e2e
gitleaks dir . --config .gitleaks.toml --redact
gitleaks git . --config .gitleaks.toml --redact
```

E2E authentication requires `APP_ENV=e2e`, `E2E_AUTH_ENABLED=true`, and a non-committed random `E2E_AUTH_SECRET` of at least 32 characters. Trusted setup code may call `issue_e2e_token`; no HTTP issuer exists. Tokens live at most 15 minutes. Production startup refuses this mode.

Production uses Cognito and injected database/provider secrets. Never compile E2E mode for production, commit credentials/storage state, or expose execution inputs/raw outputs in audit records. For troubleshooting, verify migration head, tenant claim, Agent lifecycle/published version, assignment readiness, permission/action decision, correlation ID, and linked discovery/tool execution in that order.
