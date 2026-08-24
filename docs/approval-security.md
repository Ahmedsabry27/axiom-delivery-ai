# Approval Security and Human Control

## Authorization and tenancy

Permissions are explicit: `actions.create|read|read_all|edit|execute|verify|cancel|admin`, `approvals.request|read|read_all|approve|delegate`, and `policies.read`. Existing platform administrators retain administrative compatibility. Every lookup includes tenant identity; evidence and linked records must be in that tenant.

## Separation of duties

MEDIUM, HIGH and RESTRICTED actions cannot be approved by their requester. Service identities cannot make human decisions. Assigned approvals reject other reviewers; delegation cannot target the requester. The executor and verifier must be distinct. Multiple approval decisions must come from distinct actors.

## Binding and tamper resistance

- Approval binds tenant, action ID, action version, policy ID/version and exact payload fingerprint.
- Material edits increment the version and supersede pending approval.
- Approval decisions are append-only at the ORM layer and retain evidence/policy snapshots.
- Execution is idempotent, allowlisted and row-locked; rejected, expired, stale, unknown or draft-only actions have no execution path.
- Notifications are visible only to the target user in the same tenant.
- Audit summaries pass through the shared secret-redaction boundary.

## Tested negative paths

Automated tests cover self-approval, foreign-tenant discovery/execution, expired approval, stale action version, missing evidence, unknown/external policy denial, rejected execution, duplicate execution replay and attempted mutation of an approval decision. The isolated live browser specification also encodes the persona journey and negative checks in `frontend/e2e-live/action-center-live.spec.ts`.
