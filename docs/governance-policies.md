# Governance policies

Policies are durable records keyed by tenant and `policy_key`, with explicit category, version, priority, conditions, effect, reason codes, lifecycle, author, approver, and review date. The lifecycle is `DRAFT -> PENDING_APPROVAL -> ACTIVE -> RETIRED`.

Updating an active policy creates a new draft version; it never mutates the active record. Submission and activation are separate operations. Activation requires a human identity with `policies.activate`, and the author cannot approve their own version. Attempts by service/agent identities fail closed and are audited.

Simulation evaluates an explicit synthetic scenario against exact declarative conditions. It returns the matched conditions and proposed decision without changing persisted or active state. This is a deterministic evaluator, not arbitrary executable policy code.
