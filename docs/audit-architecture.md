# Audit architecture

Governance writes append-only `audit_logs` records with an event UUID, timestamp, tenant, actor and actor type, action/result, resource, policy/model/provider/tool identifiers, execution/approval correlation, trace ID, severity, and sanitized metadata. Payloads pass through the existing recursive secret-redaction layer before persistence.

ORM update and delete guards reject modification. The public API offers list, detail, verification, and permission-gated bounded export; it exposes no update or delete route. Consequential policy and model lifecycle actions emit audit records in the same database transaction as their state changes.
