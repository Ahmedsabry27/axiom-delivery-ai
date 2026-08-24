# Dependency domain model

`delivery_dependencies` is the authoritative dependency record. `delivery_dependency_endpoints` stores its provider (`SOURCE`) and consumer (`TARGET`) as typed, tenant-scoped endpoints. Core fields cover the reference, type and relationship, lifecycle status, owner/provider/consumer ownership, acknowledgement, required/committed/forecast/actual dates, review dates, critical-path flag, external marker, source, metadata, and optimistic `version`.

Supported endpoint types are portfolio, programme, project, team, sprint, release, milestone, epic, work item, defect, system, service, environment, vendor, and external party. Internal endpoints must resolve inside the current tenant. External placeholders are allowed only when the dependency is explicitly external; they never reference or reveal another tenant.

Relationship types are centralized in `dependency_intelligence.py`: `BLOCKS`, `REQUIRES`, `DELIVERS_TO`, `DEPENDS_ON`, `ENABLES`, `PRECEDES`, the shared environment/resource types, and data, technical, business, approval, and external dependencies.

The lifecycle is `IDENTIFIED → PROPOSED → ACKNOWLEDGED → PLANNED → IN_PROGRESS`, with controlled at-risk, blocked, escalated, resolved, closed, and cancelled branches. Escalation requires a reason. Closed/cancelled records cannot silently become active; reopen is explicit. Every material change appends `delivery_dependency_history` and an audit event.

Saved simulations use `delivery_dependency_scenarios`; reviewed AI detections use `detected_dependency_candidates` and their evidence association. Proposals reuse the durable `proposed_actions` model. Evidence and related RAID records remain shared rather than copied.
