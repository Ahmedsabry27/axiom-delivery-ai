# Approval permissions

Visibility and decisions use `ApprovalAuthorizationService`. Effective access considers the authenticated tenant, actor, permissions, role/group assignment, explicit assignment, delegation, status, expiry, subject type, and separation of duties. Cross-tenant or invisible IDs use the established non-enumerating boundary.

Evidence is returned only after the approval and linked action have passed authorized tenant-local lookup.
