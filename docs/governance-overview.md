# Governance overview

AX-EP10 adds tenant-scoped governance and AI operations control planes. `/governance` derives its measures from policies, access reviews, audit events, and incidents; `/ai-operations` derives measures from runtime executions, usage records, and incidents. Unknown measures remain `null` and render as **Not available**, never as invented zeroes.

Administrators can inspect versioned policies, permissions, access reviews, audit evidence, retention controls, governed models, evaluations, incidents, usage, costs, and budgets. Every API uses the authenticated tenant and explicit permission checks. Production has no governance mock-data fallback.

Apply Alembic revision `c3e5f7a9b1d4` before starting the API. The frontend reads the backend through `VITE_API_URL`.
