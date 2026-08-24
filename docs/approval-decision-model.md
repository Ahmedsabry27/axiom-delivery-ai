# Approval decision model

AX-AP01 reuses the AX-EP07 `ApprovalRequest` and append-only `ApprovalDecision` models. Backend capabilities determine whether approve, reject, request-changes, or delegate controls are rendered. Decisions remain transactional, tenant-scoped, state-checked, version-bound, and subject to separation of duties.

Rejection and requested-change decisions require a reason. Approval changes action eligibility but does not imply successful execution or verification.
