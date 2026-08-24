# Approval and Action Center

AX-EP07 adds the human control plane for delivery actions. An AI recommendation or a user-authored intervention becomes a durable `ProposedAction`; it never becomes an external write merely because it was generated. The workflow is:

```text
recommendation → proposed action → policy evaluation → human decision
→ allowlisted adapter → independent verification → append-only audit
```

## Durable records

- `delivery_proposed_actions` stores the exact payload, original payload, origin, requester/agent, target, risk, bound policy version, lifecycle timestamps, expiry, failure and optimistic action version.
- `approval_requests` links the existing governance envelope to an action version and assignee. Tool-runtime approvals under `/api/v1/approvals` remain compatible and separate.
- `action_approval_decisions` is append-only and retains actor, rationale, evidence snapshot and policy snapshot.
- `action_executions` records adapter, attempt, idempotency key, trace, request snapshot and safe result/failure.
- `action_verifications` records an independent system-of-record read and evidence.
- `action_policy_definitions` stores tenant-scoped versioned policy materializations.
- `action_notifications` stores tenant/user-scoped actionable notifications and routes.

Alembic revision `f8d1b6c3e540` is forward-only from `e7c0a5f2b438`. Its upgrade, downgrade and re-upgrade are validated on SQLite; production startup continues to require migration-head parity.

## API surface

- `GET|POST /api/actions`, `GET|PATCH /api/actions/{id}`
- `POST /api/actions/{id}/submit|execute|retry|verify|cancel`
- `GET /api/approvals`, `GET /api/approvals/{id}`
- `POST /api/approvals/{id}/approve|reject|request-changes|delegate`
- `GET /api/action-policies`, `POST /api/action-policies/evaluate`
- `GET /api/notifications`, `POST /api/notifications/{id}/read`
- `/api/action-catalog` preserves the earlier integration action catalogue without route ambiguity.

Request models reject unknown fields. Reads, transitions, evidence, approvals, executions, verifications and notifications are tenant-scoped. A foreign tenant receives `404` for entity lookups.

## User experience

`/actions` is the responsive Action Center with lifecycle tabs, risk/status counters, safe empty/error states, a proposal composer and URL-addressable action details. Details place policy, evidence, exact payload, approval/execution history and linked audit events in one review surface.

`/approvals` is the responsive Approval Inbox. The reviewer sees what will change, target, action version, separation-of-duties requirement, evidence and exact payload before approving, rejecting, requesting changes or delegating with rationale.

My Day includes assigned action approvals. Command Center attention includes pending approvals plus failed execution or verification. RAID, Dependency Intelligence and Copilot proposals populate the extended durable action model and can enter the center; unsupported legacy action types remain reviewable but fail closed for execution.

No Jira, Azure DevOps, email, Slack, calendar or workflow side effect was enabled by this epic.
