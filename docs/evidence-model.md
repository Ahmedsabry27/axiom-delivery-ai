# Evidence model

Evidence stores tenant, related entity type/id, source system and record, timestamps, source URL, summary, and content hash. Recommendations and proposed actions link to evidence through tenant-aware association tables. API retrieval and action association use tenant-scoped repositories.

Evidence authorization currently proves tenant ownership. Centralized entity-level authorization, freshness presentation, and immutable audit linkage remain required before production approval.
