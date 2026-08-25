# AX-AGI01 Agile Performance

AX-AGI01 adds a tenant-scoped Agile intelligence slice without creating a second delivery domain. The React views call a typed repository, authenticated FastAPI routes delegate to `AgileIntelligenceService`, and the service reads persisted SQLAlchemy observations and OKRs. Metric arithmetic remains in backend services.

## Routes

- `/agile-performance`
- `/agile-performance/predictability`
- `/agile-performance/flow`
- `/agile-performance/backlog`
- `/agile-performance/quality`
- `/agile-performance/risk`
- `/agile-performance/team-health`
- `/agile-performance/okrs`
- `/agile-performance/okrs/:objectiveId`

The existing ceremony workspace remains authoritative under `/meetings/ceremonies` and `/meetings/ceremonies/:ceremonyId/:tab`.

## API and access

The `/api/agile-performance` API exposes summary, metric, attention, objective and check-in operations. Reads require `agile.metrics.read` or `agile.okrs.read`; mutations require `agile.okrs.manage`. Every query is tenant scoped, writes are audited, and objective updates use optimistic versions.

Missing data is returned as `null`/`UNKNOWN`, with missing inputs and evidence metadata. The frontend does not calculate or invent metric values.
