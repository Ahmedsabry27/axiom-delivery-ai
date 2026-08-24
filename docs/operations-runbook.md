# Operations runbook

Before startup, provide production database/auth/model configuration through approved secret injection, set mock mode and schema creation false, apply Alembic migrations, and verify `/ready`. Stop promotion on migration mismatch, failed security gates, or synthetic data. No production deployment was performed during AX-H02.

## AX-EP05 RAID operations

Apply `cd backend && ../.venv/bin/alembic upgrade head`; expected head is `d6b9f4e1a327`. Verify `/ready`, `/api/raid/summary`, and an authenticated `/api/raid` request before serving `/raid`. Monitor API/query latency, error rate, candidate validation failures, duplicate rate, accepted/dismissed candidate rates, overdue count, and unknown scores through the established logging/metrics stack. A migration failure must be rolled back at the database transaction/backup boundary and corrected with a forward-only revision; never edit an applied migration. No automatic production seed or external RAID mutation is permitted.

## AX-EP06 Dependency Intelligence operations

Apply `cd backend && ../.venv/bin/alembic upgrade head`; expected head is `e7c0a5f2b438`. Verify `/ready`, authenticated `/api/dependencies/summary`, `/api/dependencies/graph`, and `/dependencies`. Stop promotion if the graph exceeds its configured limit, a cycle is present in existing active data, tenant/evidence authorization fails, or the migration is not current.

Monitor graph/API/path/impact latency, node and edge counts, traversal depth, cycle and graph-limit rejections, unknown-health rate, scenario count, candidate decisions, and proposal creation. High graph-limit rejection rates require tighter user scope or reviewed aggregation, not a raised unbounded limit. Scenarios and proposals never execute externally. Recover migration failures using the established database backup/transaction boundary and a new forward-only revision.
