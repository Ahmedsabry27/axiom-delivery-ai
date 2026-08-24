# AX-H01 Production Readiness and Gap Closure

Date: 2026-08-14

## Decision

**NO-GO FOR AX-EP05**

The repository is not production-ready. Durable delivery records, tenant-scoped repositories, evidence authorization, persistent proposed actions/feedback, production mock guards, and isolated tests were added. However, production delivery read paths remain synthetic, the complete delivery schema is not yet represented, the full backend suite is not green, static analysis is not at zero findings, TypeScript is not comprehensively checked, and clean-environment browser/API evidence is incomplete.

## Executive summary

| Area | Result | Evidence |
|---|---|---|
| Backend targeted tests | Pass | 20 passed |
| Backend full tests | Fail | 504 passed, 1 failed; intermittent Jira continuation metadata |
| Frontend tests | Pass | 72 passed in 23 files |
| Frontend lint | Pass | ESLint zero errors |
| Frontend production build | Pass with warning | mock disabled; ChatPage 858.28 kB |
| Migrations | Pass | clean SQLite upgraded to `aae403476012 (head)` |
| Backend lint | Fail | Ruff reports 505 existing findings |
| Production delivery reads | Fail | Command Center, My Day, and Sprint endpoints still return synthetic data |
| Tenant isolation | Partial pass | repository/direct-ID tests pass; broader API matrix incomplete |
| External writes | Pass for new action flow | proposed actions stop at internal draft/review states |

## Changes completed

- Added durable tenant-owned delivery models for portfolios, programmes, projects, teams, sprints, releases, work items, defects, RAID items, evidence, recommendations, proposed actions, feedback, and conversation delivery context.
- Added additive Alembic revision `aae403476012` and validated it from an empty database through head.
- Added tenant-mandatory repositories with scoped list/get and cross-tenant evidence rejection.
- Replaced process-local proposed-action and Copilot-feedback storage with database persistence.
- Added direct tenant-scoped action/evidence retrieval APIs and persistence/isolation tests.
- Isolated tests from developer `.env` trusted-host and schema-create settings.
- Corrected database-secret precedence.
- Added backend and frontend production guards preventing mock delivery mode.
- Restored a green frontend lint/test/build path with mock mode explicitly disabled.

## Open gaps

| ID | Severity | Gap | Owner | Required closure evidence |
|---|---|---|---|---|
| H01-01 | P0 | Command Center, My Day, attention, recommendation, and Sprint APIs still synthesize data | Backend | API integration tests against persisted records |
| H01-02 | P0 | Milestone and explicit dependency entities/relationships are absent | Backend/Data | migration plus tenant and referential-integrity tests |
| H01-03 | P0 | Full backend suite is nondeterministic: Jira continuation can omit `parameter_extraction` | Runtime | repeated full-suite green runs |
| H01-04 | P0 | Ruff reports 505 findings; no zero-warning backend gate | Engineering | clean lint/static-analysis run |
| H01-05 | P0 | TypeScript sources are not covered by a strict typecheck gate | Frontend | `tsc --noEmit` and ESLint TS coverage |
| H01-06 | P0 | Required clean-environment browser and API user-journey validation is incomplete | QA | recorded authenticated journey and API smoke evidence |
| H01-07 | P1 | Delivery writes are not connected to the established audit-event chain | Backend/Security | immutable audit tests for create/update/review |
| H01-08 | P1 | Evidence entity authorization validates tenant but not a centralized entity-policy service | Security | authorization matrix tests |
| H01-09 | P1 | Copilot delivery-context persistence is modeled but not wired to conversation endpoints | Copilot | conversation reload/context tests |
| H01-10 | P1 | ChatPage production chunk is 858.28 kB | Frontend | code splitting and bundle-budget gate |
| H01-11 | P1 | Secret/dependency scans were not completed in a clean CI-equivalent environment | DevSecOps | scan artifacts and reviewed exceptions |

## Required remediation order

1. Replace every synthetic production delivery read with repository/service queries and return explicit empty/insufficient-data states.
2. Complete the delivery schema and additive migration for milestones and dependencies.
3. fix the Jira continuation race and prove repeatability.
4. Establish zero-error Ruff, mypy/typing, TypeScript, and dependency/secret scan gates.
5. Wire audit and conversation context persistence.
6. Run clean-environment API and browser journeys, then reassess the gate.

No AX-EP05 work should start while any P0 above remains open.
