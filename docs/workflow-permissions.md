# Workflow permissions

All management reads and mutations resolve the tenant from the authenticated `custom:tenant_id` claim. Unknown and cross-tenant numeric IDs both return the same not-found response. Actor IDs come from the trusted `sub` claim and are recorded in version and activity rows.

The schema includes workflow access grants, but full role/action enforcement and effective user-workflow-agent-tool-policy authorization are deferred security qualification items.
