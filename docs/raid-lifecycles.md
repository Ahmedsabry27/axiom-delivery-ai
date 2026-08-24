# RAID lifecycles

Lifecycle rules live in `app.delivery.raid_intelligence.STATUS_TRANSITIONS`.

- Risk: Identified → Assessed → Open → Mitigating/Escalated/Realized → Closed.
- Assumption: Identified → Validating → Validated/Invalidated/Expired → Closed.
- Issue: Open → Investigating/Resolving/Escalated → Resolved → Closed.
- Dependency: Identified → Acknowledged → In Progress/Blocked/At Risk → Resolved → Closed.
- Decision: Proposed → Under Review/Pending → Approved/Rejected/Deferred → Implemented/Superseded.
- Action: Open → In Progress/Blocked/Overdue → Completed/Cancelled.

Invalid jumps return 422. Every accepted transition checks the optimistic version, records actor, trace, previous/new status, time, and new record version, then writes both RAID history and the shared audit stream. Terminal transitions require a closure/resolution note. `COMPLETED` or `IMPLEMENTED` requires linked evidence when `completion_evidence_required` is enabled. Reopening is permitted only where explicitly listed.
