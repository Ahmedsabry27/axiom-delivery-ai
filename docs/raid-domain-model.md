# RAID domain model

`DeliveryRAIDItem` remains the single RAID aggregate. Shared fields cover tenant, reference, title/description, type, status, priority, owner, identification/due/review/closure dates, source, audit actors, version, exposure snapshots, and attention reasons.

Typed delivery links include programme, project, team, sprint, release, milestone, work item, defect, and dependency. `DeliveryRAIDRelationship` supports additional authorized delivery links; `DeliveryRAIDRelatedItem` supports RAID-to-RAID relations. Both are tenant-scoped and repository-validated.

Type-specific fields are persisted on the aggregate:

- Risk: probability, impact, residual values, trigger, response, mitigation, contingency.
- Assumption: validation owner/date/method/status.
- Issue: severity, containment, resolution plan, root cause.
- Dependency: typed dependency, critical path, blocked-since, required date.
- Decision: statement in description, decision owner, due date, rationale.
- Action: description, owner, due date, completion-evidence requirement.

Evidence uses `DeliveryRAIDEvidence`; reviews use `DeliveryRAIDReview`; append-only record activity uses `DeliveryRAIDHistory`. Recommendations and proposed actions reuse their shared tables through typed `raid_id` foreign keys. Candidates and their evidence links use `DetectedRAIDCandidate` and `DetectedRAIDCandidateEvidence`.

Every aggregate and join carries `tenant_id`. Applicable links use composite `(tenant_id, id)` foreign keys. Polymorphic secondary relationships are accepted only after the repository verifies the target in the authenticated tenant.
