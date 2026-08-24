# Approval authorization model

Approval authorization is enforced by `ApprovalAuthorizationService`; frontend visibility is advisory only. All lookups first scope by tenant, so foreign-tenant identifiers return the existing not-found response without disclosing approval data.

Viewing requires `approvals.read` plus one relationship: requester, assigned user, active delegated target represented by the current typed assignment, assigned role/group membership, or explicit tenant-scoped `approvals.read_all`. Requester access is read-only unless the requester is independently decision-eligible and separation-of-duties permits it.

Decisions require `approvals.approve`, a human identity, and the current user/role/group assignment. Unassigned approvals remain approval-pool items for permitted human approvers. Status, expiry, action-version freshness, duplicate-decision, evidence, and separation-of-duties checks remain in the transition service. `approvals.read_all` grants visibility, not an assignment bypass. Delegation additionally requires `approvals.delegate`; the existing model records `delegated_from`, `delegated_to`, and replaces the assigned user. Time-bounded or scoped delegation is not advertised and remains deferred.

Roles and Cognito groups are normalized to lowercase and matched exactly against `assigned_role`; substring and display-name matching are prohibited. Permissions are still parsed centrally by `AgentIdentity.from_claims` from the space-delimited `scope` and explicit `permissions` list.

List queries apply the same relationship predicate used by detail authorization. API responses expose safe capabilities (`canView`, `canApprove`, `canReject`, `canRequestChanges`, and `canDelegate`) so read-only viewers do not receive decision controls. The backend repeats authorization for every transition.

The Playwright identity helper keeps a navigation-stable test override. This fixes the prior condition where the requester initialization script overwrote the approver token after `page.goto`; it does not alter production authentication.
