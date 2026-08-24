# Action State Machines

## Proposed Action

```text
DRAFT ──submit──> PENDING_APPROVAL ──approve──> APPROVED
  │                    │                    │
  │                    ├─reject──────────> REJECTED
  │                    └─changes─────────> CHANGES_REQUESTED ──edit──> DRAFT
  └─cancel───────────> CANCELLED

APPROVED ──execute──> EXECUTING ──success──> VERIFYING ──verify──> VERIFIED
                           └─failure──────> FAILED       └─mismatch──> VERIFICATION_FAILED
```

Expiry can terminate a pending or approved action. Execution is never inferred from approval. Retry creates another execution attempt and still requires a currently bound approval.

## Approval

`PENDING` transitions to `APPROVED`, `REJECTED`, `CHANGES_REQUESTED`, `CANCELLED`, `EXPIRED` or `SUPERSEDED`. A material edit supersedes the prior request; decisions already recorded remain immutable. Restricted rules may keep the request pending until distinct human decisions reach the required count.

## Concurrency

- Editing requires `expected_version`; stale clients receive `409 STALE_ACTION_VERSION`.
- Execution locks the action row on databases that support `SELECT FOR UPDATE`.
- `(tenant_id, proposed_action_id, idempotency_key)` is unique. A replay returns the existing execution.
- Approval decisions are unique per approval, action version and actor.
- Invalid and terminal transitions return explicit `409` errors.
