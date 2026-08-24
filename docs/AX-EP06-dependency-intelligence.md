# AX-EP06 Dependency Intelligence

Dependency Intelligence turns tenant-authorized, persisted dependency relationships into deterministic delivery analysis. The primary UI is `/dependencies`; the API root is `/api/dependencies`.

The capability includes a searchable register, summary cards, a bounded directed graph with a tabular accessibility alternative, critical-path classification, bottleneck findings, read-only delay scenarios, evidence, candidate review, audit history, and durable proposed interventions. Command Center, My Day, RAID, Sprint Intelligence, and Copilot consume the same dependency records.

No external action is executed. Jira, Azure DevOps, messaging, calendars, ownership, scope, and authoritative delivery dates are unchanged by analysis or proposals. Candidate acceptance and lifecycle changes require authenticated human action.

The additive Alembic revision is `e7c0a5f2b438`, following `d6b9f4e1a327`. It preserves the pre-EP06 dependency and RAID records and adds typed relationship, history, scenario, and detection fields/tables.

Known boundary: AX-EP07 owns the full Approval Center. EP06 proposals stop at `DRAFT`, `PROPOSED`, or `PENDING_APPROVAL`.
