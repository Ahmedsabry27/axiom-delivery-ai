# Audit event integrity

Application audit events are append-only. The application exposes only an append operation,
sanitizes summaries with the common credential redactor, and SQLAlchemy rejects updates and
deletes of `AuditLog` objects during normal application sessions. Events contain tenant, actor,
action, target, correlation, timestamp, and bounded safe summaries; they must never contain raw
credentials, document bodies, tool inputs, or tool outputs.

This is application-layer immutability, not cryptographic tamper resistance. Database
administrators can still alter the storage directly. Deployments requiring evidence that remains
trustworthy against database administrators must forward these events to an external,
tamper-resistant audit sink with independent retention and access controls.

Explicit deny has governance precedence over approval and allow. Approval-required decisions are
evaluated only after deny rules and must be backed by a persisted, unexpired, policy-bound request.
