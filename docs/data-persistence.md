# Data persistence

Delivery records use SQLAlchemy and Alembic revision `aae403476012`. Every repository requires a non-empty tenant identifier and scopes direct-ID and list queries by tenant. Proposed actions and Copilot feedback are durable database records. The current model covers core hierarchy, sprint/work/defect/RAID data, evidence, recommendations, and conversation context; milestones and dependency relationships remain blocking gaps.

Runtime schema creation is a local-only fallback. Production must use migrations.
