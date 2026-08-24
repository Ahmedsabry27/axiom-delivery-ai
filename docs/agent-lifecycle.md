# Agent Lifecycle

The current canonical lifecycle is `draft → published → enabled`, with `disabled`, `archived`, and `error` operational states. Invalid transitions return a conflict. All mutations use optimistic `If-Match` locking and append an agent activity event.

Published versions are immutable snapshots. Updating an agent creates a new version. Disabling prevents new normal executions; archiving retains historical versions and executions.

Condition: explicit `IN_REVIEW`, `APPROVED`, `PAUSED`, and `RETIRED` vocabulary and AX-EP07 publication approval linkage remain to be added through a forward-only migration and lifecycle service extension.
