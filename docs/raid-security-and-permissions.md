# RAID security and permissions

Every `/api/raid` endpoint requires the existing Bearer-token authentication dependency. Tenant and actor claims are mandatory. Repository queries always start with the authenticated tenant; inaccessible objects return non-disclosing errors.

Capabilities are `raid.read`, `raid.create`, `raid.update`, `raid.assign`, `raid.review`, `raid.close`, `raid.manage_evidence`, `raid.manage_relationships`, `raid.review_candidates`, and `raid.admin`. Existing legacy identities with an empty permission claim retain authenticated compatibility; explicit permission sets are enforced and `raid.admin` is the override.

Controls include allowlisted filters/sorts, bounded pagination, escaped search wildcards, Pydantic size/type validation, composite tenant foreign keys, evidence authorization, relationship target validation, cross-tenant rejection, optimistic version conflicts (409), transaction rollback, safe error bodies, and append-only audit events. Source URLs are rendered only as safe external anchors and Markdown is not accepted by the RAID APIs.

Negative tests cover list/detail/search isolation, foreign evidence, candidate review, mutation permissions, cross-tenant relationships, proposed interventions, and Copilot evidence. No tokens, secrets, chain-of-thought, or excessive source content is stored in RAID audit metadata.
