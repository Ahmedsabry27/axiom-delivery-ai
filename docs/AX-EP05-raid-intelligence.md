# AX-EP05 — RAID Intelligence

Axiom Delivery AI is an independent R&D prototype. All demonstration data is synthetic.

AX-EP05 adds a durable, tenant-scoped unified register for Risks, Assumptions, Issues, Dependencies, Decisions, and Actions. `/raid` reads the authenticated tenant's persisted records through `/api/raid`; production has no mock fallback and no process-local RAID store.

The implementation centralizes deterministic exposure, attention, hygiene, duplicate screening, and lifecycle validation in `app.delivery.raid_intelligence`. The tenant repository owns authorized CRUD, evidence, relationships, reviews, history, candidates, and optimistic concurrency. Command Center, My Day, Sprint Intelligence, and Copilot consume the same persisted aggregate.

AI-assisted detection stops at a durable candidate. Acceptance, dismissal, merging, lifecycle changes, recommendations, and proposed interventions require authenticated human requests and are audited. Proposed interventions can only be `DRAFT`, `PROPOSED`, or `PENDING_APPROVAL`; no email, Teams message, meeting, Jira/Azure DevOps record, or other external action executes.

Revision `d6b9f4e1a327` is additive after `c5a8e3d0f216`. Advanced dependency-graph reasoning and automated graph propagation are deferred to AX-EP06.
