# AX-DEMO-01 outcome

## Completion decision

AX-DEMO-01 INCOMPLETE

## Executive summary

A safe, deterministic, persistent core demonstration workspace is implemented through the normal database and APIs. The critical identity narrative, portfolio hierarchy, delivery execution, releases, RAID, dependencies, milestones, outcomes, investment, evidence, meetings, users, and safe integrations are connected. Full breadth across actions/approvals, agents/workflows, governance/AI Operations, conversations, notifications, and authenticated browser coverage remains incomplete.

## Seed architecture and controls

The explicit `app.seed.demo_data` CLI uses stable UUIDv5 keys and SQLAlchemy merge/upsert behavior. It requires development/test, `ALLOW_DEMO_SEED=true`, and exact tenant `axiom-demo`. Reset requires `--confirm-tenant axiom-demo`, deletes tenant-scoped rows in dependency order, and preserves other tenants. There is no startup hook, HTTP seed route, secret, or external request.

## Tenant, identities, counts, and narrative

The tenant is `Axiom Demo Enterprise`, classification `DEMO`, FY27 Q1, GBP, Europe/London. Fourteen fictional identities are persisted without passwords. Seed output: 1 portfolio, 3 programmes, 8 projects, 6 teams, 9 sprints, 18 work items, 5 releases, 8 milestones, 3 dependencies, 5 RAID items, 28 evidence records, 5 outcomes, 15 investment snapshots, 8 meetings, 6 integrations, and one recommendation.

`DEP-017` connects Identity Modernisation, `IDAM-241`, the Identity Integration Complete milestone, Atlas 3.2, `RISK-008`, evidence, and an intervention recommendation. Portfolio and delivery metrics remain backend-calculated.

## Investment reconciliation

Current programme snapshots reconcile to £18.40M approved, £8.15M actual, and £19.25M forecast. Four portfolio periods provide trend data. Amounts use `Numeric(19,4)` and no currency conversion.

## Commands and results

See `docs/demo-data-guide.md`. The first and second isolated database executions returned identical counts and passed relationship validation. Dry-run rolled back and subsequent persisted validation remained green. Six focused safety/idempotency/reset/database-target tests and 16 combined seed/foundation/portfolio tests passed. No migration was added.

## Browser, frontend, and backend validation

Backend full suite: 585 passed. Frontend lint, strict TypeScript, 38 files / 125 tests, and the mocks-disabled production build passed. The build contained no demo-data or release-fixture chunk. The trusted `/api/delivery/metadata` response derives `Demo workspace` classification from persisted portfolio metadata, and the application layout renders the indicator. Authenticated browser validation remains pending because this session exposed no browser instance.

## Files created

- `backend/app/seed/__init__.py`
- `backend/app/seed/demo_data.py`
- `backend/tests/test_demo_seed.py`
- The four AX-DEMO-01 documents.

## Files modified

- `backend/app/api/delivery.py`
- `frontend/src/components/layout/EnterpriseLayout.jsx`
- `README.md`

## Known limitations and recommended next step

Extend the manifest through the supported action/approval state machine, agents/workflows, governance/AI Operations, meeting findings/transcripts, conversations, defects, notifications, and additional RAID/dependency/milestone counts. Then run authenticated desktop/tablet/mobile browser journeys and security scans before changing the completion decision.
