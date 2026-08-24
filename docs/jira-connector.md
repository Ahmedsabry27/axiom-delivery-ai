# Jira Cloud connector

The connector supports the existing bounded Jira REST adapter plus durable simulator-backed projects, sprints, issues, mappings, fingerprints, incremental cursors, sync runs, and quarantine. Jira remains source-authoritative for workflow state, sprint, points, and assignee. Custom fields require explicit mappings.

Create, update, comment, assignment, and transition capabilities are approval-required. The generic Integration Hub execute endpoint returns `WAITING_FOR_APPROVAL`; arbitrary REST payloads and delete operations are not exposed. Live 3LO synchronization, boards/changelog pagination, webhook verification, canonical delivery-repository writes, and sandbox validation remain deferred.
