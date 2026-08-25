# Axiom Delivery AI

Detailed current-state and target AWS architecture diagrams are available in the [architecture pack](docs/architecture/README.md).

Production-readiness status: **NO-GO FOR AX-EP05**. See `docs/AX-H02-final-gap-closure-report.md` for verified results and remaining blockers.

## AI Delivery Copilot

Open `/copilot` for the evidence-backed conversational delivery workspace. It preserves the existing conversation history, SSE runtime, agent registry, and OpenAI/Bedrock provider abstraction while adding delivery-context selection, structured evidence responses, confidence and limitation display, feedback, and approval-only action drafts. See [the Copilot guide](docs/ai-delivery-copilot.md) and the related response, evidence, streaming, and proposed-action contracts in `docs/`.

Copilot organization routes provide persisted conversation history, saved insights with immutable evidence snapshots, canonical evidence and proposed actions, versioned governed prompt templates, user favorites, and durable privacy-safe feedback. Additive migration `f1b3d5e7a9c2` creates the Copilot persistence layer and conversation archive/context metadata. Runtime requests continue through the canonical pre-invocation model and budget gate; no Copilot route bypasses actions or approvals.

## Sprint Intelligence

Open `/sprints` for the cross-team portfolio and `/sprints/:sprintId` for deterministic health, metrics, burndown, transparent forecasting, goal confidence, work-item risk, blockers, backlog readiness, quality signals, system-level Agile anti-patterns, comparisons, and human-reviewed intervention drafts. Formulas, thresholds, missing-data handling, forecast limitations, and mock/API behavior are documented in [Sprint Intelligence](docs/sprint-intelligence.md) and the related sprint documents in `docs/`.

> Evidence-led delivery. Confident decisions.

Axiom Delivery AI is an enterprise delivery intelligence platform that consolidates delivery signals, identifies emerging risks, connects dependencies, automates governance workflows, and supports evidence-backed decision-making.

The repository directory remains `ai-delivery-platform`; the current user-facing product name is Axiom Delivery AI. This is an independent R&D prototype, not an official PwC product. Do not use real client information during development.

## Epic AX-EP01 — Platform Foundation

The foundation includes canonical delivery-domain contracts, centralized metric definitions and safe calculations, authenticated delivery metadata endpoints, a mock/API repository boundary, aligned frontend summary contracts, shared page states, complete navigation, persisted local sidebar preference, a development-only design-system showcase, and synthetic demonstration data.

- Domain model: `docs/delivery-domain-model.md`
- Metric catalogue: `docs/delivery-metrics.md`
- Development showcase: `/dev/design-system` while running Vite in development mode
- Foundation APIs: `/api/delivery/metadata`, `/api/delivery/metric-definitions`, and `/api/delivery/health`

Delivery persistence is intentionally contract-first in AX-EP01. No database migration is required yet; the documented forward-only migration plan is the starting point for the persistence work.

## Delivery Command Center

The authenticated landing page is the Axiom Command Center. It combines portfolio health, sprint predictability, risks, dependencies, delivery trends, attention items, and evidence-backed Axiom Recommendations. Recommendation actions produce reviewable proposals only; they do not mutate external systems.

Navigation is organized into My Work, Delivery, Intelligence, Automation, and Administration. Existing Axiom AI Copilot (chat), Agents, Workflows, Governance, Integrations, and Settings capabilities retain their routes; planned delivery modules use shared-layout `Coming soon` pages.

The UI is an independent R&D prototype with a warm, consulting-inspired visual language. It is not an official PwC product and contains no PwC logo, proprietary font, or protected brand asset.

### Available experience routes

- `/command-center` — portfolio delivery overview and recommendations
- `/copilot` — existing streaming chat with delivery evidence presentation
- `/raid` — RAID register, dependency map, and AI-detected dependency review
- `/agents`, `/workflows`, `/integrations`, `/tool-governance`, `/settings` — preserved platform capabilities

Shared tokens in `frontend/src/index.css` define charcoal navigation, warm surfaces, neutral borders, burgundy, vermilion, amber and gold accents, plus Georgia/Inter display and interface font stacks.

The inherited platform architecture is intentionally preserved; delivery-management capabilities are added incrementally.

## Project structure

- `backend/` — FastAPI application, Alembic migrations, AI providers, agents, runtime orchestration, workflows, tools, governance, audit, persistence, metrics, and tests.
- `frontend/` — React/Vite UI, Cognito authentication, chat/conversations, runtime views, dashboard components, and tests.
- `docs/` and `architecture_handover/` — inherited architecture and operational documentation.
- `observability/`, `grafana/`, and `prometheus/` — monitoring configuration (runtime metric data is not committed).
- `.github/workflows/` — inherited CI/CD definitions. Review all deployment targets and secrets before enabling them.
- Docker/Compose, Amplify, and ECS files are inherited deployment definitions; this setup provisions nothing.

## Environment configuration

Copy `.env.example` to `backend/.env` and `frontend/.env`, retaining only the variables each component needs. Never commit either file.

The template contains local-safe placeholders only. Supply dedicated development resources for PostgreSQL, Cognito, AWS/Bedrock, OpenAI, and enterprise integrations. Do not reuse production resource identifiers or credentials. When Cognito values are absent on `localhost`, the frontend uses a clearly identified local-development user; non-local builds remain fail-closed and require complete Cognito configuration.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run `pytest` from `backend/`. Some integration/live tests require explicitly configured external services.

When delivery persistence migrations are introduced, apply them using the repository’s existing safe migration wrapper:

```bash
cd backend
python scripts/run_alembic_safe.py
```

## Frontend setup

```bash
cd frontend
npm ci
npm run dev
```

The Vite server uses `VITE_API_URL`. Build and test with `npm run build` and `npm test`.

## Connected demonstration workspace

AX-DEMO-01 seeds fictional, persistent data only for the exact `axiom-demo` tenant. Apply migrations, then run:

```bash
cd backend
APP_ENV=development ALLOW_DEMO_SEED=true ../.venv/bin/python -m app.seed.demo_data --tenant-id axiom-demo --scenario enterprise-transformation --reference-date 2026-10-06
```

Use `--dry-run` or `--validate` for non-mutating checks. Reset requires both `--reset-demo-tenant` and `--confirm-tenant axiom-demo`. Production/staging, missing flags, and non-demo tenant IDs are refused. Run the backend normally and the frontend with `VITE_USE_MOCK_DELIVERY_DATA=false`; authenticate with a controlled development identity whose tenant claim is `axiom-demo`. Demo personas and removal details are documented in [the demo data guide](docs/demo-data-guide.md).

Set `VITE_USE_MOCK_DELIVERY_DATA=true` (the default when unset) to use the local, non-client demonstration dataset. Set it to `false` when a compatible `GET /api/delivery/command-center` endpoint is available. The mock values live behind a typed repository rather than in page components.

## Current inherited architecture

The platform includes FastAPI and React/Vite, Cognito authentication, conversations and chat, AI agents, runtime orchestration and planning, workflow execution, tool discovery, MCP/native tools, governance and audit, OpenAI and AWS Bedrock providers, database integration and Alembic migrations, streaming/SSE, and Prometheus/Grafana monitoring.

## RAID Intelligence

AX-EP05 provides an authenticated persisted `/raid` workspace for Risks, Assumptions, Issues, Dependencies, Decisions, and Actions. Apply Alembic revision `d6b9f4e1a327`, start the backend, and run the frontend with `VITE_USE_MOCK_DELIVERY_DATA=false`. RAID candidate detection remains evidence-required and human-reviewed; interventions remain internal proposals only. See `docs/AX-EP05-raid-intelligence.md`.

## Development direction

AX-EP06 adds persisted Dependency Intelligence at `/dependencies`, backed by `/api/dependencies` and Alembic revision `e7c0a5f2b438`. It includes a tenant-scoped directed graph, deterministic cycle/path/impact analysis, health and priority scoring, read-only scenarios, evidence-backed candidates, and human-reviewed proposed interventions. See `docs/AX-EP06-dependency-intelligence.md`.

AX-EP06 proposal records feed the AX-EP07 Approval and Action Center; dependency execution remains blocked until an explicit adapter is approved.

## Approval and Action Center

AX-EP07 provides the human control plane at `/actions` and `/approvals`. Evidence-backed proposed actions are classified by deterministic versioned policy, reviewed by authorized humans with separation of duties, executed only through an explicit internal adapter allowlist, independently verified, notified and audited. External Jira, Azure DevOps, email, messaging and calendar operations remain draft-only. Apply Alembic revision `f8d1b6c3e540` and see `docs/approval-and-action-center.md` plus `docs/AX-EP07-outcome.md`.

## Current limitations

- Delivery metrics are demonstration data unless the delivery API mode is enabled.
- Placeholder modules do not yet provide delivery-system integrations.
- Proposed RAID and Copilot actions can enter the Approval and Action Center; external targets remain draft-only.
- Dependency scenarios are simulations; they do not rewrite authoritative dates. Formal critical-path duration/float requires complete timing data.

## Agent Management

The governed Agent Management workspace is available at `/agents`, with creation at `/agents/new` and URL-addressable overview, configuration, capabilities, knowledge, models, evaluations, executions, versions, access, and test views beneath `/agents/:agentId`. It reuses the canonical registry, runtime orchestrator, model allowlist, tool and knowledge catalogues, evaluation framework, budget controls, approvals, and audit activity.

New agents are drafts. Configuration updates use optimistic locking and immutable version snapshots. Tool visibility never grants execution permission, mutating tools remain approval-bound, and test executions use the existing durable runtime in explicit test mode. AX-DEMO-01 seeds configured versioned agents when run against the local development database. See [Agent Management](docs/agent-management.md), [Agent lifecycle](docs/agent-lifecycle.md), and [AX-AG01 outcome](docs/AX-AG01-outcome.md) for current functionality and documented conditions.

## Governance and AI Operations

AX-EP10 adds durable, tenant-isolated governance at `/governance`, governed models at `/models`, and operational evidence at `/ai-operations`. Apply Alembic revision `c3e5f7a9b1d4`. Policy and model activation require authorized human separation of duties; audit events are redacted, append-only, and hash-chained; unknown metrics and costs remain unavailable rather than being invented. See [docs/governance-overview.md](docs/governance-overview.md) and [docs/AX-EP10-outcome.md](docs/AX-EP10-outcome.md).

## Safety

No cloud infrastructure, remote Git repository, or production connection is configured by the clone process. Before enabling deployment workflows, review every AWS, Cognito, database, API URL, CORS, storage, queue/topic, and integration setting for isolation.
# Portfolio Intelligence

Portfolio routes are available under `/portfolio`, with programme, project, investment, milestone, and insight subpages. Data comes from authenticated tenant-scoped delivery records via `GET /api/delivery/portfolio`; production routes do not use mock data. Health and attention metrics are calculated in the backend, missing evidence remains explicit, and mixed currencies are not aggregated. See [Portfolio Intelligence](docs/portfolio-intelligence.md) and [AX-EP11 outcome](docs/AX-EP11-outcome.md).
# Workflow management

Workflow management is available at `/workflows`, with `/workflows/new` and URL-backed overview, designer, configuration, triggers, inputs, approvals, runs, versions, access, and test subpages. Definitions use start/end, agent, tool, condition, approval, human-input, and notification nodes. New definitions are drafts; version snapshots are durable, published definitions are immutable, and edits use `If-Match` optimistic locking.

The supported configuration trigger types are Manual, Scheduled, Domain event, and Approval completion. Approval/runtime handoff, trigger dispatch, and safe external test execution remain known limitations; see [the AX-WF01 outcome](docs/AX-WF01-outcome.md). No production workflow fixtures are used.

Run the frontend with `cd frontend && npm run dev`; validate it with `npm run lint`, `npm run type-check`, and `npm run build`. Run the backend with the repository's standard Uvicorn command, apply schema changes with `alembic upgrade head`, and execute workflow tests with `pytest -q tests/test_workflow_api.py tests/test_workflow_persistence.py tests/test_workflow_execution.py tests/test_runtime_tenant_isolation.py tests/test_api_workflow_execution.py`.
# Approval Workbench

Approval management is available at `/approvals`, with submitted, history, delegations, and URL-backed detail tabs for overview, proposal, evidence, impact, execution, and activity. It reuses AX-EP07 decision authorization, separation of duties, immutable decisions, Action Center execution, independent verification, notifications, and audit.

Backend capabilities control approve, reject, request-changes, and per-approval delegation. Requesters cannot approve their own controlled proposals; approval never implies successful execution or verification. Reusable scoped delegation and escalation remain known limitations documented in [the AX-AP01 outcome](docs/AX-AP01-outcome.md).
# Integration and Data Quality Hub

Integration administration uses `/integrations`, `/integrations/catalog`, `/integrations/new`, and URL-backed integration detail routes. Existing MCP servers are available through `/mcp-servers`; Jira is labelled beta because connection, discovery, and governed capabilities work but durable data synchronization does not. Other catalogue connectors remain planned.

Authentication stores and returns secret references only. Mapping, synchronization, quality, quarantine, and lineage routes explicitly report unavailable data until their durable persistence exists. See [the AX-EP12 outcome](docs/AX-EP12-outcome.md) for the support matrix, validation commands, and limitations.

AX-EP12A adds simulator-backed Jira, Confluence, Outlook Calendar, and Teams Meetings connector operations under the same hub. Apply revision `b8d0f2a4c6e9`, use the documented localhost callbacks `/api/integrations/atlassian/callback` and `/api/integrations/microsoft/callback`, and configure deployed HTTPS callback URLs in the provider registrations. Non-secret client IDs/tenant selections may be environment configuration; client secrets and tokens must use `env://` or `aws-secrets://` references. `simulator://` contains no credential and is test/demo-only. Start a manual sync from a connector detail page; mappings, cursors, runs, quality, lineage, and subscription status populate through authenticated APIs. Live webhook/change-notification validation requires an explicitly authorized secure endpoint and dedicated sandbox tenants. See [OAuth and secrets](docs/integration-oauth-and-secrets.md), [permission manifest](docs/integration-permission-manifest.md), and the honest [AX-EP12A outcome](docs/AX-EP12A-outcome.md). Run backend focused tests with `pytest -q tests/test_connector_pack.py tests/test_enterprise_integrations.py` and frontend validation with `npm run validate`.

# Model Registry and Operations

The governed model workspace uses `/models`, `/models/catalog`, `/models/register`, and URL-backed model detail tabs. It reads the existing registry, pricing, usage, evaluation, incident, and audit records; registration creates drafts and never activates traffic automatically. See [Model registry workspace](docs/model-registry-workspace.md) and the honest [AX-MD01 outcome](docs/AX-MD01-outcome.md).

# Enterprise Settings

Settings are available at `/settings` with profile, preferences, appearance, notifications, workspace, delivery, reporting, AI, data, features, and activity subpages. Effective values resolve from platform defaults through tenant overrides to permitted user preferences. Workspace changes are typed, versioned, administrator-controlled, and audited; safety controls and secrets are never editable. Apply migration `a7c9e1f3b5d8` and see [Settings workspace](docs/settings-workspace.md), [Settings hierarchy](docs/settings-hierarchy.md), and [AX-ST01 outcome](docs/AX-ST01-outcome.md).

# Axiom Design System

Semantic tokens live in `frontend/src/index.css`, shared primitives and templates in `frontend/src/components/design-system`, and the development-only showcase at `/dev/design-system`. Use [token guidance](docs/axiom-design-tokens.md), [component guidance](docs/axiom-component-guidelines.md), and [page templates](docs/axiom-page-templates.md). Run `npm run lint`, `npm run type-check`, `npm test -- --run`, and `VITE_USE_MOCK_DELIVERY_DATA=false npm run build`; browser accessibility and visual tests require the project Playwright environment.

New pages must use Axiom tokens, shared components, and page templates. New page-specific UI primitives require documented justification.
# Ceremony and Lessons Intelligence

Ceremony routes live under `/meetings/ceremonies`; governed lessons live under `/knowledge/lessons`. The module reuses Meeting Intelligence transcripts/findings, Action Center proposals, and authorized evidence. Checklist templates and historical snapshots are versioned. Required-evidence completion and not-applicable reasons are enforced by the backend. Checklist, evidence, and effectiveness scores remain separate and return missing dimensions.

Local connected records can be created after migration with:

```bash
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m scripts.seed_ceremony_intelligence
../.venv/bin/pytest -q tests/test_ceremony_intelligence.py tests/test_meeting_intelligence.py
```

See `docs/ceremony-intelligence.md`, `docs/ceremony-checklist-templates.md`, `docs/ceremony-effectiveness-scoring.md`, and `docs/lessons-learned.md`.

# Agile Performance and OKR Intelligence

Agile Performance is available at `/agile-performance`, with backend-calculated predictability, flow, backlog, quality, risk, team-health and OKR views. Missing observations remain explicitly unknown and team-health aggregates require at least five anonymous responses. See [the implementation guide](docs/AX-AGI01-agile-performance.md), [metric catalogue](docs/agile-metric-catalogue.md), and [AX-AGI01 outcome](docs/AX-AGI01-outcome.md).
