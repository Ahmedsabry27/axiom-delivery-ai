# Agent Management

The Agent Management workspace uses the canonical tenant-scoped agent registry at `/api/v1/agents`. The Automation sidebar opens `/agents`; creation uses `/agents/new`; detail capabilities are addressable beneath `/agents/:agentId/*`.

The catalogue supports server-side search, lifecycle, owner, model, environment, sort, and pagination. Metrics identify their visible-page scope. Mobile records render as cards. Authentication and object authorization remain backend responsibilities.

Configuration, assignments, test execution, execution history, analytics, activity, and versions reuse the existing application and runtime services. Production fixture fallback is not used.
