# Model governance

The governed model registry records provider identifiers, family, capabilities, allowed and prohibited use cases, permitted data classifications and regions, context limit, lifecycle status, version, author, and approver. Configuration changes produce a new draft version.

Only `ACTIVE` models pass runtime allowlist validation. Unknown, draft, pending, retired, disallowed-classification, or disallowed-use-case selections fail closed. Approval and activation require human control and separation from the author. Provider-price synchronization and live provider capability discovery are deferred integrations.
