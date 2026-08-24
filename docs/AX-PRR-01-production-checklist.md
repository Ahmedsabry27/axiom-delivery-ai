# AX-PRR-01 Production Checklist

Overall: **NO-GO — PRODUCTION READINESS NOT ESTABLISHED**

## Release gates

- [ ] Versioned Git commit, clean worktree, reviewed release tag
- [ ] Every P0 epic production ready
- [ ] No P0 or P1 gaps
- [ ] Frontend mock mode fails closed and is disabled in production
- [ ] Frontend clean install, lint, strict types, all tests, and production build pass three times
- [x] Backend full suite passes twice (578 passed in each run)
- [x] Combined concurrency-sensitive runtime/continuation/action/budget set passes ten consecutive runs
- [x] Ruff check and format check
- [x] Single Alembic head and clean isolated upgrade to head
- [ ] Upgrade from an independently preserved previous-head database
- [x] Production configuration fails closed when unsafe/missing
- [ ] Fully configured production-equivalent FastAPI startup/readiness
- [ ] Persisted authenticated Journeys A–G
- [ ] Desktop, tablet, and mobile browser coverage
- [ ] Complete negative tenant/entity/financial/evidence security matrix
- [x] Filesystem secret scan
- [ ] npm production dependency audit
- [ ] Python dependency audit
- [ ] Static security scan and vulnerability triage
- [ ] Performance requirements and measured p50/p95/p99
- [ ] Backup/restore rehearsal with RTO/RPO evidence
- [ ] Deployment and rollback rehearsal
- [ ] Incident/on-call, provider outage, key rotation, and audit export drills

## Epic completion

- [ ] AX-EP01 production ready
- [ ] AX-EP02 production ready
- [ ] AX-EP03 production ready
- [ ] AX-EP04 production ready
- [ ] AX-EP05 production ready
- [ ] AX-EP06 production ready
- [ ] AX-EP07 production ready
- [ ] AX-EP08 production ready
- [ ] AX-EP09 production ready
- [ ] AX-EP10 production ready
- [ ] AX-EP11 production ready

Release authorization must remain withheld until every unchecked P0/P1 gate has objective evidence and this audit is repeated.
