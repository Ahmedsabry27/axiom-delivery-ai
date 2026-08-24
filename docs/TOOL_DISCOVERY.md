# Sprint 14 — Dynamic Tool Discovery and Governance

Sprint 14 extends the Sprint 11 registry and executor, Sprint 12 native tools,
and Sprint 13 MCP adapters. It introduces no parallel execution path.

## Pipeline and ranking

The planner extracts a bounded structured intent and requests a small candidate
set. Tenant, status, agent assignment, permission, policy, health, environment,
classification, risk, and cost are deterministic filters. Only eligible tools
enter hybrid retrieval. Recommendations are rechecked by Tool Executor.

Strategy 1.0.0 uses:

    0.28 semantic + 0.24 lexical + 0.14 exact-name
    + 0.08 capability + 0.10 input compatibility
    + 0.06 historical success + 0.04 health
    + 0.025 risk + 0.02 latency + 0.015 cost

Permissions and hard policies are never score penalties. Explicit deny overrides
allow. Destructive tools and always-approval profiles require approval. Low
confidence or ambiguous requests return clarification rather than execution.

## Embeddings and storage

EmbeddingProvider is replaceable. The safe default, feature-hash-v1, produces
128-dimensional normalized embeddings locally and deterministically. It supports
batching and caching, incurs no provider cost, and transmits no metadata. Vectors
are JSON for compatibility with PostgreSQL and SQLite tests. A pgvector-backed
provider can replace this boundary without changing discovery domain logic.

Search documents contain sanitized names, descriptions, category, provider,
tags, and safe input-field descriptions. Credentials, secret-like fields,
connections, resource contents, prompts, defaults, and execution input are
excluded. Fingerprints prevent unnecessary reindexing.

## Governance and privacy

Marketplace status immediately affects registry visibility and discovery.
Assignments support users, roles, groups, and agents. Structured policies are
versioned and tenant-scoped with draft, active, superseded, and archived states.
Rejected candidate records omit tool identity, and API summaries never reveal
unauthorized inventory counts.

Discovery records store normalized intent instead of raw requests. Execution
analytics reuse ToolExecution. Missing cost data is labeled unavailable.

## APIs

- /api/v1/tool-discovery: search, simulation, details, feedback, index status
- /api/v1/tool-marketplace: catalog, status, assignments, governance
- /api/v1/tool-governance: policy lifecycle and simulation
- /api/v1/tool-analytics: measured discovery and execution analytics

Simulation never invokes tools. Index administration, policies, marketplace
mutation, and analytics require tool-administrator authorization.

## Testing

    cd backend
    .venv/bin/alembic upgrade head
    .venv/bin/pytest -q tests/test_tool_discovery.py tests/test_discovery_benchmark.py
    .venv/bin/pytest -q
    .venv/bin/ruff check app/tool_discovery app/api/tool_discovery.py
    .venv/bin/mypy app/tool_discovery --follow-imports=skip

    cd ../frontend
    npm test
    npm run lint
    npm run build

The offline benchmark enforces zero unauthorized recommendations and cross-tenant
leakage, and an initial top-1 threshold of two-thirds across eligible reference
cases. Threshold changes require a reviewed, versioned benchmark update.
