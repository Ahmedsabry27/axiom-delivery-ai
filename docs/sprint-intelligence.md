# Sprint Intelligence

Authenticated routes `/sprints` and `/sprints/:sprintId` provide cross-team and selected-sprint intelligence. The UI consumes one repository contract in mock or API mode. `VITE_USE_MOCK_DELIVERY_DATA=true` uses centralized synthetic Phoenix/Sprint 24 data; false calls the authenticated `/api/sprints` foundation.

The detail view separates deterministic health and forecasting from evidence-backed recommendations. It covers burndown, scope change, at-risk work, blockers, readiness, quality, system-level anti-patterns, historical comparison, and approval-only intervention drafts. No Jira, Azure DevOps, calendar, messaging, assignment, or sprint-scope mutation occurs.

Axiom Delivery AI is an independent R&D prototype. All demonstration data is synthetic. Sprint Intelligence evaluates delivery systems—not individual employee performance.
