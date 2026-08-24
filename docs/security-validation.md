# Security validation

AX-H01 added tenant-scoped direct-ID and evidence-association tests and retained proposal-only external action behavior. Production configuration rejects mock delivery data and runtime schema creation. Database secret-field precedence was corrected and secret-redaction tests pass.

Release remains blocked pending complete secret scanning, dependency vulnerability review, entity-level evidence authorization, audit-event integration, broader IDOR testing, and reviewed CORS/trusted-host configuration in a clean environment.
