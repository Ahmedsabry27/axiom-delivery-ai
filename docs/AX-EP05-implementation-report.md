# AX-EP05 RAID Intelligence implementation report

## 1. Executive summary

AX-EP05 delivers a durable, tenant-scoped RAID Intelligence capability for Axiom Delivery AI. Risks, Assumptions, Issues, Dependencies, Decisions, and Actions share one persisted aggregate and API family. The module provides deterministic scoring, lifecycle validation, attention and hygiene analysis, duplicate screening, evidence and delivery relationships, detected-candidate review, proposed interventions, structured Copilot answers, and integrations with Command Center, My Day, and Sprint Intelligence.

Axiom Delivery AI is an independent R&D prototype. Demonstration data is synthetic. No external action is executed by this epic.

## 2. Baseline inspected

The repository had no `AGENTS.md` and no committed Git baseline; all existing files were untracked and were preserved. The inspected migration head was `c5a8e3d0f216`. AX-EP01 through AX-EP04 capabilities, the delivery models and repositories, tenant authentication, evidence, proposed actions, audit, Copilot, Command Center, My Day, Sprint Intelligence, and existing browser suites were inspected before implementation.

Baseline gates were 509 backend tests, 72 frontend tests, zero Ruff findings, strict TypeScript, production build, and the existing six-case responsive Playwright suite.

## 3. Architecture decisions

- Extended the existing `DeliveryRAIDItem`; no parallel or duplicate RAID aggregate was created.
- Kept all production records in SQLAlchemy persistence; there is no process-local RAID record store.
- Centralized lifecycle, scoring, attention, hygiene, and duplicate rules in one deterministic domain service.
- Centralized tenant-scoped data access, entity authorization, history, and optimistic concurrency in one repository.
- Reused the established authentication, permission, evidence, audit, conversation, recommendation, and proposed-action models.
- Detection stops at an evidence-backed candidate. Only a human-authenticated request can accept, dismiss, merge, or propose an intervention.

## 4. RAID domain model

The shared item supports reference, type, title, description, lifecycle status, priority, owner, dates, source fields, version, audit actors, evidence count, attention state, direct delivery links, typed relationships, related RAID items, reviews, history, recommendations, and proposed actions.

Type-specific data includes risk probability/impact/inherent and residual exposure/mitigation; assumption validation owner/date/method/result; issue severity/root cause/resolution; dependency critical path/upstream/downstream/required date; decision owner/options/outcome/decision date; and action owner/due/completion state.

## 5. Schema and migration

Revision `d6b9f4e1a327` follows `c5a8e3d0f216`. It additively extends RAID, recommendation, proposed-action, and Copilot response tables and creates evidence-link, relationship, related-item, history, review, detected-candidate, and candidate-evidence tables with tenant-aware constraints and indexes. Existing RAID references are backfilled as `LEGACY-{id}` before becoming required.

The migration test upgrades a representative `c5a8e3d0f216` database, verifies preserved data and new schema, downgrades to `c5a8e3d0f216`, and upgrades again. A separate clean database upgrade to head also passed.

## 6. Repository implementation

`RAIDRepository` requires tenant and actor identity. It implements CRUD, filtering, escaped search, bounded pagination, allowlisted sorting, version conflicts, evidence links, typed relationships, related items, history, reviews, summaries, attention, hygiene, duplicate screening, candidates, accept/dismiss/merge, and tenant-safe entity resolution. Transactions commit explicitly at API boundaries and roll back on validation, not-found, conflict, or integrity errors.

## 7. APIs

The `/api/raid` family includes list/create/detail/update, summary, attention, hygiene, heatmap, lifecycle transition, assignment, evidence links, relationship links, history, review, close, candidate list/detect/accept/dismiss/merge, executive and weekly reports, recommendations, proposals, and RAID Copilot responses.

List queries support type, status, exposure, probability, impact, priority, programme, project, team, sprint, release, milestone, owner, source, search, overdue, stale, unowned, critical-path, date range, pagination, and validated sorting.

## 8. UI implementation

`/raid` and `/raid/:raidId` now load authenticated persisted APIs and provide six type tabs, summary cards, a unified desktop table, mobile cards, search, filters, sorting preference, pagination, loading/empty/partial/error/retry states, type-aware creation, accessible risk heatmap, durable detail drawer, evidence, typed relationships, activity history, reviews, status changes, candidate review/edit/accept/dismiss, and proposal-only interventions.

The UI never falls back to synthetic production RAID responses. Small-screen cards, semantic tables/tabs, labeled forms, keyboard-operable heatmap cells, non-colour status text, and focusable drawers were validated in browser coverage.

## 9. Risk scoring

Risk exposure is `probability × impact`, using integer levels 1–5. Bands are LOW, MEDIUM, HIGH, and CRITICAL. Missing probability or impact returns `UNKNOWN`/`INSUFFICIENT_DATA`; it is never silently converted to zero. Residual exposure is computed independently from residual inputs.

## 10. Hygiene rules

Deterministic findings cover missing owners, missing required type fields, overdue dates, stale reviews, missing evidence, aged open records, unvalidated assumptions, incomplete mitigation/resolution data, and lifecycle inconsistencies. Findings include rule, severity, explanation, and recommended correction.

## 11. Candidate detection

Candidates persist type, title, description, bounded confidence, authorized evidence, affected entities, suggested fields, duplicate candidates, limitations, detector/model identifiers, trace, reviewer state, and version. Detection requires at least one tenant-authorized evidence item and valid structured input.

The review panel shows evidence provenance, supports editing candidate fields before acceptance, and requires an explicit human submission. The accepted item carries authorized evidence and reviewed values into durable RAID persistence.

## 12. Duplicate detection

Deterministic screening compares normalized titles, descriptions, delivery scope, ownership, dates, and related context. It returns candidate records, confidence, and reasons. It never merges automatically; merge remains an authenticated human decision and preserves evidence.

## 13. Evidence and authorization

Evidence IDs are resolved inside the authenticated tenant before linking or returning content. Composite tenant constraints protect durable links. Detail and Copilot responses return only authorized evidence. Cross-tenant evidence, relationship, search, candidate, proposal, and direct-object access paths are covered by negative API and browser tests.

## 14. Recommendations and interventions

Recommendations require evidence. Proposed interventions link to RAID and optional authorized evidence, require approval, and are restricted to `DRAFT`, `PROPOSED`, or `PENDING_APPROVAL`. Creation adds audit and RAID history records. Responses state `externalWrites: false`; Jira, Azure DevOps, email, meetings, and messaging systems are not mutated.

## 15. Command Center integration

Open RAID records flow into the existing attention model through the centralized attention calculation. The integration uses the shared persisted aggregate and does not maintain a secondary projection in process memory.

## 16. My Day integration

Owned RAID items and pending detected candidates appear in My Day with their type, urgency, due context, and persisted description. The page supports all new RAID item kinds with an explicit safe icon fallback.

## 17. Sprint Intelligence integration

Sprint detail returns linked open RAID records. A critical linked risk lowers goal confidence using the existing health calculation, so sprint forecasts and health explain the same persisted risk visible in the RAID register.

## 18. Copilot integration

RAID Copilot answers use the shared repository and authorized evidence. Structured responses include summaries, top items, evidence, confidence/limitations, and proposal boundaries. Conversation messages, response/evidence links, trace IDs, and audit records persist. Copilot does not execute external actions.

## 19. Audit and observability

Create, update, transition, assignment, review, evidence, relationship, candidate, recommendation, proposal, report, and Copilot operations produce correlated audit/history records. Existing request IDs, structured logs, API latency/error metrics, database metrics, and traces apply to the new endpoints.

## 20. Security controls

Controls include existing bearer authentication, mandatory tenant/actor claims, explicit RAID capabilities, tenant-first repository predicates, composite tenant constraints, entity/evidence authorization, safe errors, bounded schema fields, escaped search, allowlisted sort/filter fields, optimistic version conflicts, validated lifecycles, and transaction rollback.

Gitleaks and the repository secret scanner found no secrets. `npm audit --omit=dev --audit-level=high` found zero vulnerabilities. Python audit retains the formally accepted `ecdsa 0.19.2 / PYSEC-2026-1325` limitation: the timing issue affects ECDSA signing/key operations, while this application only calls `jose.jwt.decode` with an RS256 allowlist. There is no direct `ecdsa`, ES256, signing, key-generation, or ECDH runtime path and no upstream fix version. The existing review date remains 2026-09-14.

## 21. Tests

- Backend: 516/516 passed twice consecutively.
- Focused RAID, migration, and seed suite: 8/8 passed.
- Frontend: 23/23 files and 73/73 tests passed.
- Ruff: zero findings; 375 files format-clean.
- Configured mypy scope: six production/bootstrap files, zero issues.
- Strict TypeScript and ESLint: passed.
- Production build: passed.

Coverage includes deterministic scoring, missing-data behavior, hygiene, duplicate detection, six lifecycles, CRUD, concurrency, evidence, tenant isolation, permissions, candidate review, proposals, Copilot, audit, cross-module propagation, migration round-trip, production configuration, direct-object references, and restart durability.

## 22. Playwright results

- Existing responsive fixture suite: 6/6 passed on desktop, tablet, and mobile.
- Authenticated persisted live matrix: 24/24 passed.
- The live matrix ran at 1440×900, 1024×768, 768×1024, and 390×844.
- Each viewport covered existing Agents, Command Center/My Day/Sprint continuity, the full RAID positive journey, and negative tenant paths.
- RAID coverage proves persisted summary, R-031 detail, critical exposure, owner, typed relationship, evidence, durable review, keyboard heatmap filtering, candidate edit and human acceptance, evidence-backed Copilot, proposed intervention, audit history, reload persistence, and cross-tenant rejection.

The optional in-app browser runtime reported no available browser instance. This did not replace or skip mandatory browser validation; the repository Playwright suites launched Chromium and passed.

## 23. Migration results

Clean upgrade to `d6b9f4e1a327` passed. Upgrade from `c5a8e3d0f216`, representative legacy-data preservation, downgrade to `c5a8e3d0f216`, and re-upgrade passed in `test_raid_migration.py`.

## 24. Full validation commands and results

| Command | Result |
|---|---|
| `cd frontend && npm ci` | passed, 903 packages installed from lockfile |
| `cd frontend && npm run validate` | ESLint, strict TypeScript, 73 tests, production build passed |
| `cd frontend && npx playwright test --config playwright.config.ts` | 6/6 passed |
| `cd frontend && npx playwright test --config playwright.live.config.ts` | 24/24 passed |
| `cd backend && ../.venv/bin/pip install -r requirements-dev.txt` | clean declared dependency check passed |
| `cd backend && ../.venv/bin/ruff check .` | zero findings |
| `cd backend && ../.venv/bin/ruff format --check .` | 375 files format-clean |
| configured `mypy --follow-imports=skip ...` | zero issues in six configured files |
| `cd backend && ../.venv/bin/pytest -q && ../.venv/bin/pytest -q` | 516/516 passed, then 516/516 passed |
| focused RAID/migration/seed tests | 8/8 passed |
| FastAPI import and local startup/readiness | passed |
| clean Alembic upgrade and migration round-trip | passed |
| `.venv/bin/python scripts/scan_secrets.py` | zero findings |
| `gitleaks dir . --redact` | no leaks found |
| `npm audit --omit=dev --audit-level=high` | zero vulnerabilities |
| `pip-audit -r requirements-prod.txt` | one formally accepted non-applicable advisory; no applicable high/critical finding |
| `git diff --check` | passed |

## 25. Files created

- `backend/app/api/raid.py`
- `backend/app/delivery/raid_intelligence.py`
- `backend/app/delivery/raid_repository.py`
- `backend/alembic/versions/d6b9f4e1a327_add_raid_intelligence.py`
- `backend/tests/test_raid_intelligence.py`
- `backend/tests/test_raid_migration.py`
- `frontend/src/components/raid/RAIDSummaryCards.jsx`
- `frontend/src/components/raid/RiskHeatmap.jsx`
- `frontend/src/components/raid/DetectedRAIDReview.jsx`
- `frontend/src/components/raid/RAIDItemDrawer.jsx`
- `frontend/src/components/raid/RAIDItemForm.jsx`
- `frontend/e2e-live/raid-live.spec.ts`
- the six required RAID documents and this report

## 26. Files modified

- Backend delivery models/exports/domain/read service/Copilot service, application router, and live E2E seed
- Frontend router, RAID page/tests/service, My Day page, global field style, and live Playwright configuration
- `README.md`, operations runbook, testing/validation guide, and cross-module data-flow guide

No file was modified outside `/Users/ahmedsabry/ai-delivery-platform`; disposable acceptance databases and signed short-lived test state were created only under `/private/tmp`.

## 27. Deferred AX-EP06 capabilities

Advanced dependency graph intelligence, automated graph propagation, graph simulation, and cross-programme graph recommendations are deferred to AX-EP06. AX-EP05 only stores and authorizes the relationships required for future graph work.

## 28. Known limitations

- Historical trend confidence requires multiple persisted reporting periods.
- Detection is deterministic in this prototype; future model-backed detection must pass the same schema and evidence gates.
- Legacy authenticated identities with an empty permission claim retain compatibility; explicit permission claims are enforced and should become mandatory after migration.
- The existing large `ChatPage` production chunk warning remains; the RAID chunk is independently lazy-loaded.
- Backend tests emit existing dependency deprecation warnings.
- The accepted ECDSA transitive advisory must be reassessed on 2026-09-14 or immediately if an ES algorithm is introduced or a fixed dependency becomes available.

## 29. Remaining findings

There is no open AX-EP05 P0 correctness, tenant-isolation, evidence-authorization, migration, test, or applicable high/critical security finding. Remaining items are the accepted ECDSA limitation, existing build/deprecation warnings, and AX-EP06 scope above.

## 30. Exact commands to run the application

Backend:

```bash
cd /Users/ahmedsabry/ai-delivery-platform
source .venv/bin/activate
cd backend
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```bash
cd /Users/ahmedsabry/ai-delivery-platform/frontend
npm ci
cp -n ../.env.example .env
npm run dev
```

Supply isolated development Cognito values in `frontend/.env`, or use the documented signed E2E mode only for disposable local browser testing. If a port is occupied, stop the existing process or choose another explicit port.

## 31. Readiness recommendation for AX-EP06

All AX-EP05 P0 and regression gates passed. The persisted, tenant-safe relationship foundation is ready for AX-EP06 graph intelligence without external mutation authority.

GO FOR AX-EP06
