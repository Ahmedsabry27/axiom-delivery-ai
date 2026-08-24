# AX-EP06 Implementation Report — Dependency Intelligence

## 1. Entry-gate result

PASS. `AX-H03-enforced-readiness-report.md` was satisfied and AX-EP05 ended `GO FOR AX-EP06`. No EP05 condition affected dependency persistence, RAID linkage, tenant/evidence authorization, proposals, audit, migration, APIs, or tests. The inspected Alembic head was `d6b9f4e1a327`; the baseline passed before implementation.

## 2. Executive summary

AX-EP06 implements durable, tenant-scoped Dependency Intelligence. Persisted provider/consumer edges now drive a register, accessible directed graph, deterministic cycle/path/impact analysis, critical-path classification, health/priority scoring, bottleneck findings, saved read-only scenarios, evidence-backed candidate review, Copilot responses, and human-reviewed proposed interventions. No external action executes.

## 3. Architecture decisions

The existing delivery dependency aggregate was extended rather than replaced. Typed endpoint rows remain graph edges; calculations live in `dependency_intelligence.py`; tenant/transaction rules live in `dependency_repository.py`; FastAPI only validates/orchestrates; React renders API results. Graph calculations are never delegated to an LLM.

## 4. Domain model

The dependency model now includes reference, relationship type, provider/consumer owner, acknowledgement, committed/forecast/actual resolution dates, review dates, external marker, and concurrency version. History, scenarios, detected candidates, and candidate evidence are durable. Supported endpoint and relationship enums are centralized. Provider and consumer self-links, inaccessible internal endpoints, duplicates, cycles, invalid URLs/transitions, and stale versions are rejected.

## 5. Migration revision

Additive revision `e7c0a5f2b438` follows `d6b9f4e1a327`. It extends dependency fields and indexes and creates dependency history, scenarios, candidate, and candidate-evidence tables. Existing references are backfilled deterministically. Clean upgrade, legacy-data upgrade, downgrade to the former head, and re-upgrade passed.

## 6. Repository changes

`DependencyRepository` provides tenant-scoped list/get/create/update, typed endpoint validation, graph construction, duplicate/cycle rejection, lifecycle/acknowledgement/reopen, evidence/history/scenario/candidate retrieval, safe sorting, pagination, optimistic concurrency, and explicit transaction rollback through the API commit boundary. Graph endpoint labels are resolved in grouped queries.

## 7. API implementation

Twenty-four dependency paths are registered under `/api/dependencies`: register/create, summary/attention, graph/path/impact/scenario, critical paths/bottlenecks, detected candidates, Copilot, detail/update/transition/acknowledge/reopen/evidence, upstream/downstream/history, proposals, and candidate accept/dismiss/merge. OpenAPI, authentication, capability checks, trace IDs, safe errors, bounds, and tenant predicates are present.

## 8. Graph algorithms

Construction uses adjacency/reverse-adjacency maps. Iterative DFS detects cycles, Kahn's algorithm orders a DAG, bounded BFS traverses impact, bounded DFS enumerates paths, and fan-in/fan-out plus impact signals identifies bottlenecks. Limits are 5,000 nodes, 20,000 edges, depth 8, and 25 paths. Complexity and limits are documented in `dependency-graph-algorithms.md`.

## 9. Critical-path approach

The service deterministically selects the longest edge-count path in the authorized DAG. It returns `CALCULATED_CRITICAL_PATH` only when every edge has required-by and forecast dates. Incomplete timing yields `POTENTIAL_CRITICAL_PATH` and explicit limitations; cyclic input yields `INSUFFICIENT_DATA`. It does not claim formal float without duration data.

## 10. Cycle handling

Creation evaluates the proposed edge against the current authorized graph before insertion. A detected cycle returns the reconstructed path and rolls back. Unit, repository, API, fixture-browser, and authenticated live-browser tests prove the cycle edge is not created.

## 11. Impact propagation

Impact uses bounded downstream BFS and separates direct from indirect typed entities, including work items, sprints, milestones, releases, and teams. It reports paths, depth, assumptions, confidence, and limitations. The five-day D-018 live journey reached Sprint 24, the payment milestone, and Release 4.

## 12. Scenario analysis

Delay scenarios compare baseline and scenario results and explicitly return `simulation: true` and `authoritativeRecordsChanged: false`. They are persisted only after explicit Save, can be retrieved after reload/restart, are audited, and never change delivery dates or execute recommendations.

## 13. Dependency health

`dependency-health-v1` applies the documented schedule, status, ownership/acknowledgement, evidence freshness, downstream impact, resolution confidence, and review-hygiene dimensions. Green/amber/red thresholds are centralized. Missing minimum inputs produce `UNKNOWN` with completeness and limitations rather than a healthy default.

## 14. Priority scoring

`dependency-priority-v1` deterministically scores critical path, late forecast, blocked state, release/milestone/sprint impact, downstream concentration, acknowledgement/ownership/date hygiene, aging, evidence freshness, external state, and escalation. Triggered factors and affected entities explain the capped score and band.

## 15. Bottleneck analysis

Bottleneck output includes node, fan-in, fan-out, priority, deterministic basis, affected dependencies, and limitations. Connectivity is only reported as a delivery bottleneck when status or criticality supplies an impact signal.

## 16. AI detection

Detected candidates are durable, status-controlled, linked to authorized persisted evidence, and expose possible duplicate/cycle data, confidence, affected entities, limitations, agent/model, and trace. Accept, merge, and dismiss are explicit review operations; the agent cannot directly create a graph edge.

## 17. Human-review boundary

Dependency creation, candidate acceptance, lifecycle mutation, scenario saving, and proposal creation require authenticated user action. Candidate suggestions and Copilot interpretation cannot override graph results. No Jira/ADO, message, calendar, ownership, scope, or resolution mutation occurs.

## 18. Proposed interventions

Dependency proposals reuse durable `ProposedAction`, authorize referenced evidence, require approval, append dependency history/audit, and return `externalWrites: false`. Status is restricted to the pre-execution boundary. The live browser test proves proposal and audit-history persistence after reload.

## 19. Cross-module integrations

Command Center dependency attention routes to `/dependencies/{id}`. My Day includes dependency work and detected candidates. Sprint Intelligence selects tenant-scoped dependency endpoints and surfaces affected sprint/work. RAID dependency records reference the same dependency ID and can open the graph. No module contains a second authoritative dependency calculation.

## 20. Copilot integration

`DEPENDENCY_INTELLIGENCE` responses use the shared graph/scoring repository and provide context, summary, health, paths, affected entities, impact, bottlenecks, recommendations, evidence, confidence, limitations, generation time, and trace. The authenticated journey verified a five-day D-018 response and `externalWrites: false`.

## 21. Audit and observability

Create/update/transition/acknowledgement/evidence/graph/path/impact/scenario/candidate/proposal/Copilot operations emit correlated audit events; material dependency changes append history. Existing request middleware records request IDs, status, and latency. Graph responses expose size/depth/trace metadata. Dedicated production dashboards for the new metric dimensions remain an operational follow-up.

## 22. Security

Authentication, capability authorization, mandatory tenant scope, typed internal-entity existence, evidence authorization, IDOR-safe responses, allowlisted sorting, pagination/traversal limits, lifecycle validation, optimistic concurrency, and transaction rollback are enforced. Repository secret scan and gitleaks found no leaks. npm production audit found zero vulnerabilities. Python audit found only `ecdsa 0.19.2 / PYSEC-2026-1325`, formally classified non-applicable because the app only verifies allowlisted Cognito JWTs and performs no ECDSA signing, key generation, or ECDH; no upstream fix exists.

## 23. Performance results

Local generated-DAG microbenchmarks on 2026-08-15:

| Size | Build | Cycle | Topological | Critical path | Depth-8 impact |
|---|---:|---:|---:|---:|---:|
| 1,000 nodes / 5,000 edges | 0.0010s | 0.0024s | 0.0005s | 0.0020s | <0.0001s |
| 5,000 nodes / 20,000 edges | 0.0066s | 0.0050s | 0.0025s | 0.0127s | <0.0001s |

The regression test enforces a five-second combined construction/cycle/topological threshold at both exact sizes. These are local algorithm measurements, not production API/SLO claims. The browser never renders an unbounded graph.

## 24. Test results

- Backend final regression: 522 tests passed twice consecutively; no failures.
- Dependency/migration/seed focused suite: 7 passed after the live fixture expansion.
- Frontend final regression: 24 files and 77 tests passed.
- Ruff: zero findings; 375 files format-clean.
- Configured mypy scope: zero issues in six production/bootstrap files.
- ESLint, strict TypeScript, production build, FastAPI import/startup, `/health`, and `/ready`: passed.

## 25. Playwright results

- Full fixture suite: 24/24 passed across desktop, tablet, and mobile projects.
- Final focused fixture dependency suite: 6/6 passed.
- Authenticated persisted Dependency live matrix: 8/8 passed at 1440×900, 1024×768, 768×1024, and 390×844 against a clean migrated disposable database.
- The live matrix verified summary, graph selection, upstream/downstream expansion, critical-path highlight, D-018 detail/owner/dates/evidence, five-day Sprint/milestone/Release impact, saved scenario, structured Copilot response, proposed escalation, history, reload persistence, cycle rollback, empty foreign graph, and cross-tenant detail/scenario/proposal rejection.

## 26. Validation commands

| Command | Result |
|---|---|
| `cd frontend && npm ci` | 903 packages installed from lockfile; zero audit vulnerabilities |
| `cd frontend && npm run validate` | ESLint, TypeScript, 77 tests, production build passed |
| `cd frontend && npm run test:e2e` | 24/24 passed |
| dependency fixture and live Playwright commands | 6/6 and 8/8 passed |
| `ruff check app scripts tests` / `ruff format --check app scripts tests` | zero / 375 clean |
| `pytest -q && pytest -q` | 522/522 then 522/522 passed |
| configured `mypy --follow-imports=skip ...` | zero issues |
| Alembic clean upgrade and migration round-trip | passed at `e7c0a5f2b438` |
| FastAPI import and TestClient `/health`, `/ready` | 200 / 200 |
| `scripts/scan_secrets.py` / `gitleaks dir . --redact` | zero findings |
| `npm audit --omit=dev --audit-level=high` | zero vulnerabilities |
| `pip-audit` | one accepted non-applicable advisory; no applicable high/critical issue |

## 27. Files created

- `backend/app/api/dependencies.py`
- `backend/app/delivery/dependency_intelligence.py`
- `backend/app/delivery/dependency_repository.py`
- `backend/alembic/versions/e7c0a5f2b438_add_dependency_intelligence.py`
- `backend/tests/test_dependency_intelligence.py`
- `backend/tests/test_dependency_migration.py`
- `frontend/src/services/dependency.service.ts`
- `frontend/src/features/dependencies/DependencyGraph.jsx`
- `frontend/src/features/dependencies/DependencyDetailDrawer.jsx`
- `frontend/src/pages/dependencies/DependencyIntelligencePage.jsx`
- `frontend/src/pages/dependencies/DependencyIntelligencePage.test.jsx`
- `frontend/e2e/dependencies.spec.ts`
- `frontend/e2e-live/dependency-live.spec.ts`
- the seven required dependency documents and this report

## 28. Files modified

- Backend delivery models/exports, main router, read service, and live E2E seed/tests
- Frontend router, Command Center, My Day, RAID, and delivery type declarations/tests
- `README.md`, operations runbook, testing/validation guide, and cross-module data-flow guide

All work remained inside `/Users/ahmedsabry/ai-delivery-platform`; browser databases/state were disposable files under `/private/tmp`. Nothing was pushed or deployed.

## 29. Known limitations

- Formal critical-path duration and float require complete per-edge timing/duration data; otherwise classification is potential with limitations.
- Scenario UI currently specializes in delay-day simulation; broader environment/scope comparisons use the same backend boundary but need richer UX.
- Graph expansion operates within the already bounded authorized subgraph; enterprise aggregation/lazy server expansion can be strengthened when real scale distributions are available.
- The production dependency-metric dashboard is not provisioned in this epic.
- The accepted transitive `ecdsa` advisory remains tracked until the authentication dependency removes it or provides a fix.

## 30. Deferred items

The full Approval Center, external Jira/ADO writes, messaging/calendar execution, meeting intelligence, release-readiness decisions, autonomous remediation, financial forecasting, resource optimization, and unsupported ML prediction remain deferred to their later epics.

## 31. Readiness recommendation for AX-EP07

All P0 dependency, migration, authorization, deterministic graph, read-only scenario, evidence, human-review, regression, security, performance, and authenticated browser gates passed. AX-EP07 may build approval workflow on the durable proposed-action boundary without enabling external actions prematurely.

GO FOR AX-EP07
