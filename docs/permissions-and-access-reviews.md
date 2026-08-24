# Permissions and access reviews

The permission catalogue and role matrix are exposed at `/api/governance/permissions` and `/api/governance/roles`. Existing authenticated claims are mapped into the catalogue; administrator wildcard access remains explicit. High-risk operations use dedicated checks such as policy activation and audit export.

Access review campaigns persist tenant, scope, reviewer, due date, status, recommendations, access items, and decisions. APIs never accept a tenant selector from the caller. Cross-tenant direct IDs return 404. Review representation is implemented; automated external identity-provider remediation is intentionally outside AX-EP10.
