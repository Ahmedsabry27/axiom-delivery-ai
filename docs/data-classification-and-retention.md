# Data classification and retention

Governed models explicitly declare allowed data classifications and regions. Runtime model checks reject classifications outside that allowlist. Audit metadata is recursively redacted before storage and export.

Retention policies are tenant-scoped and versioned by data type, retention period, deletion method, legal-hold flag, status, and effective date. Preview is always dry-run and returns candidate counts only; it never deletes data. Legal-hold workflow automation and destructive retention execution are intentionally deferred.
