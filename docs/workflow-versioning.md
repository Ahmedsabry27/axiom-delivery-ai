# Workflow versioning

Every create and draft update writes a durable `workflow_versions` snapshot. Updates require the current `If-Match` lock number. A stale writer receives `409 STALE_WORKFLOW`; a missing precondition receives `428 IF_MATCH_REQUIRED`. Published definitions reject in-place updates.

The additive migration is `f6a8c0e2b4d7` and preserves legacy workflow rows as version 1.
