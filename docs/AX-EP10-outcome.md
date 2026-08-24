# AX-EP10 Governance and Operations Outcome

## 1. Completion decision

`AX-EP10 INCOMPLETE`

The implemented foundation is substantial and its executed checks are green, but the mandatory completion contract is broader than the delivered proof. Budget thresholds are persisted but not yet enforced in runtime policy routing/blocking, and the required Copilot-to-model-to-usage-to-cost-to-trace-to-audit-to-evaluation browser journey is not yet implemented. These are blocking gaps.

## 2. Baseline confirmation

The prerequisite baseline was green before AX-EP10: backend 546/546 twice, frontend 110/110, Ruff/format/compile/import, AX-FIX-03 reliability, and AX-FIX-04 counter consistency. Post-change frontend validation passed at 115/115 twice. Post-change backend evidence is 559 tests per full run.

## 3. Architecture decisions

Governance is additive to the existing FastAPI, SQLAlchemy/Alembic, React/Vite, authenticated claims, runtime execution, approval, and audit architecture. Tenant scope comes only from the verified identity. Missing measures remain null. Policies and evaluations are declarative and deterministic. Consequential transitions and evidence are persisted transactionally.

## 4–19. Delivered capabilities

- **Governance dashboard:** persisted policy, review, incident, and audit-derived measures with honest unavailable values.
- **Policy model:** durable category/key/version/lifecycle, immutable active versions, simulation, submission, human activation, and separation of duties.
- **Permission catalogue:** claim permissions and role matrix; explicit checks protect high-risk operations.
- **Access reviews:** durable tenant-scoped campaign representation and APIs.
- **Audit:** enriched, redacted, append-only records, bounded export, trace correlation, and SHA-256 tenant hash-chain verification.
- **Integrity limitation:** no external signed/WORM anchor; legacy rows are not assigned fabricated hashes.
- **Observability:** persisted execution timelines and correlation IDs; unavailable telemetry remains null. External APM is deferred.
- **AI Operations:** persisted execution, usage, costs, evaluations, incidents, and source disclosure.
- **Model registry:** versioned configurations, human lifecycle, classification/use-case allowlist, and fail-closed selection.
- **Usage metering:** one terminal usage record per tenant/execution through a unique constraint and runtime transaction.
- **Cost calculation:** Decimal arithmetic and effective versioned prices; unknown tokens/prices produce null cost.
- **Budgets:** durable scoped limits and thresholds; runtime enforcement/routing is the blocking gap.
- **Evaluations:** versioned datasets/runs/results and deterministic security checks with model/dataset traceability.
- **Incidents:** tenant-scoped lifecycle data and unresolved-incident aggregation.
- **Retention:** versioned policy representation and deletion-free dry-run preview.

## 20. APIs

The additive router provides governance overview and policy lifecycle/simulation; permissions, roles, access reviews, audit list/detail/verify/export; models; AI Operations overview/executions/usage/costs/budgets/incidents; evaluation datasets/runs/results; and retention preview. Direct IDs are tenant scoped and mutations are permission checked.

## 21. Migration revision

Alembic `c3e5f7a9b1d4` follows `b2d4f6a8c0e1`. It creates governance/operations tables and extends `audit_logs`. Clean and previous-head upgrade tests pass.

## 22. Security controls

Tenant isolation, cross-tenant 404s, human-only activation, author/approver separation, append-only audit guards, recursive redaction, bounded permission-gated export, model fail-closed behavior, safe simulation, and production configuration were exercised. `python-jose` and its vulnerable unused ECDSA dependency were replaced by explicit `PyJWT[crypto]`; Cognito remains restricted to RS256 verification. Gitleaks, npm audit, and pip-audit are green.

## 23–25. Tests and browser evidence

- Frontend: 35 files, 115 tests, lint, strict TypeScript, and mocks-disabled build passed twice.
- Governance frontend unit tests: 5/5.
- Governance/migration/runtime/approval/production focus: 31/31.
- Responsive authenticated Playwright: 8/8 at 1440, 1024, 768, and 390 pixels.
- Negative paths cover ordinary-user denial, service-identity activation denial, cross-tenant policy denial, and audit PATCH/DELETE rejection.
- The two required full cross-module browser chains and runtime budget enforcement remain unproved; the epic is therefore incomplete.

## 26. Files created

Core additions: governance models/service/router/migration/tests; governance frontend service/pages/tests; responsive live Playwright test; and the AX-EP10 documentation set.

## 27. Files modified

Core modifications: audit model/event writer, runtime execution service, model exports, FastAPI registration, frontend router/sidebar, Cognito verifier, backend requirements, README, and this report.

## 28. Deferred scope

Permitted deferrals: deployment, external SIEM/APM, provider-price synchronization, real chargeback, legal-hold workflow, multi-region DR, external identity changes, autonomous policy changes, and real client datasets.

## 29. Known limitations and blocking gaps

1. Budget limits do not drive deterministic runtime allow/lower-cost-route/block decisions and alerts.
2. The browser journey does not prove the complete Copilot and proposal cross-module chains.
3. Audit integrity has no external trust anchor and legacy events are outside the new chain.

## 30. Exact validation commands

```text
cd frontend && npm ci
cd frontend && npm run validate                         # run twice
cd frontend && PLAYWRIGHT_REUSE_APP=true PLAYWRIGHT_BASE_URL=http://127.0.0.1:4174 VITE_API_URL=http://127.0.0.1:8012 E2E_AUTH_SECRET=<redacted> npx playwright test --config=playwright.live.config.ts governance-live.spec.ts --workers=1
cd frontend && npm audit --audit-level=high
cd backend && ../.venv/bin/ruff check app tests
cd backend && ../.venv/bin/ruff format --check app tests
cd backend && ../.venv/bin/python -m compileall -q app
cd backend && ../.venv/bin/pytest -q                       # run twice
cd backend && ../.venv/bin/pytest -q tests/test_governance_migration.py tests/test_governance_operations.py tests/test_atomic_runtime_events.py tests/test_human_approval.py tests/test_production_runtime.py
cd backend && ../.venv/bin/python -c 'from app.main import app; assert app'
cd backend && DATABASE_URL=sqlite+pysqlite:////private/tmp/ax_ep10_clean.db ../.venv/bin/alembic upgrade head
cd backend && ../.venv/bin/python -m pip_audit -r requirements.txt
gitleaks detect --source . --no-git --redact --exit-code 1
```

## 31. Production-readiness recommendation

Do not release AX-EP10 as complete. The foundation is suitable for continued integration and controlled non-production validation. Add budget enforcement and complete authenticated cross-module journeys, then rerun the entire gate.
