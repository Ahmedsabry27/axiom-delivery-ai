# Audit integrity

Each new tenant event stores canonical sorted JSON, the preceding event hash, and a SHA-256 integrity hash over the two. `/api/audit/verify` recomputes the tenant chain and reports the first mismatch without repairing history. Audit export remains redacted and capped.

Limitations: the chain is database-resident and has no externally protected anchor or SIEM/WORM replication. Rows created before revision `c3e5f7a9b1d4` have no chain fields and are treated as legacy rather than backfilled with fabricated integrity evidence. The last-row lock protects normal transactional writers; deployments requiring adversarial database-administrator protection should add an external signed anchor.
