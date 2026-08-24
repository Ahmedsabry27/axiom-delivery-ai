# Deterministic Action Policy Engine

Policy is evaluated in application code and persisted as a versioned tenant policy definition. The model or UI cannot lower risk, select an adapter or bypass approval. Evaluation returns `riskLevel`, `approvalRequired`, `requiredApprovalCount`, `separationOfDuties`, `evidenceRequired`, `verificationRequired`, `executionAllowed`, `adapter`, `draftOnly`, reasons and policy version.

## Default decision table

| Condition | Risk | Approvals | Evidence | Execution |
| --- | --- | ---: | --- | --- |
| `CREATE_RAID_ITEM`, internal | MEDIUM | 1 | Required | `INTERNAL_RAID_CREATE_V1` |
| `UPDATE_RAID_ITEM`, internal | HIGH | 1 | Required | `INTERNAL_RAID_UPDATE_V1` |
| Known action without registered adapter | HIGH | 1 | Required | Blocked, draft/review only |
| External target or external action type | HIGH | 1 | Required | Blocked, draft only |
| Critical-path or production impact | RESTRICTED | 2 | Required | Blocked unless an explicit adapter rule exists |
| Unknown action type | RESTRICTED | 2 | Required | Fail closed |

Initial taxonomy includes RAID, dependency, delivery-action, owner, decision, communication draft, scheduling, external-work-item and workflow action types. Taxonomy membership is not execution permission. Only `EXECUTION_ADAPTERS` creates an executable path.

Policy is re-evaluated at submission and execution. Approval binds the action version and SHA-256 fingerprint of the exact payload. Material edits increment the action version and supersede pending approval. Evidence must belong to the same tenant and be no more than 90 days old at submission.

Unknown actions and externally targeted writes are intentionally visible as `RESTRICTED` or draft-only so a reviewer can understand why execution is unavailable.
