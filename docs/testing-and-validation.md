# Testing and validation

Run frontend `npm run validate`, browser `npm run test:e2e`, backend `pytest -q`, backend `ruff check .`, migrations with `alembic upgrade head`, secret scan with `scripts/scan_secrets.py`, Python audit with `pip-audit -r backend/requirements.txt`, and npm audit with `npm audit --omit=dev`.

Current AX-EP05 results, accepted findings, and exact commands are in `AX-EP05-implementation-report.md`.

## AX-EP05 gates

Run `cd backend && ../.venv/bin/python -m pytest -q` twice consecutively, Ruff and format checks, FastAPI import/startup, `tests/test_raid_intelligence.py`, and `tests/test_raid_migration.py`. Run `cd frontend && npm run validate`, the fixture Playwright suite, and `npx playwright test --config playwright.live.config.ts` against the disposable migrated database and signed E2E identities. The live suite covers 1440×900, 1024×768, 768×1024, and 390×844. Finish with the secret scan, npm production audit, Python audit, and `git diff --check`. A skipped or unrun mandatory gate is not a pass.

Final AX-EP05 acceptance: backend 516/516 twice; frontend 73/73; responsive fixture Playwright 6/6; authenticated persisted Playwright 24/24; Ruff zero; 375 files format-clean; configured mypy scope, strict TypeScript, ESLint, build, migration round-trip, startup, secret scans, and npm production audit passed. Python audit retains only the formally accepted non-applicable `ecdsa 0.19.2 / PYSEC-2026-1325` finding documented in the implementation report.

## AX-EP06 gates

Run the backend suite twice, `ruff check app tests`, `ruff format --check app tests`, migration tests, FastAPI import/startup, and the dependency algorithm/API/tenant tests. Run frontend ESLint, strict TypeScript, all Vitest tests, production build, and `npm run test:e2e`. The dependency Playwright suite covers graph/evidence/scenario/proposal, cycle rejection, accessibility, and the required four viewport sizes.

Representative graph performance uses generated acyclic graphs at 1,000/5,000 and 5,000/20,000 nodes/edges. Record construction, cycle, topological, critical-path, and bounded impact timings; do not present these microbenchmarks as production latency. Finish with the secret scan, npm production audit, Python audit, and repository checks. Exact AX-EP06 evidence and accepted findings are in `AX-EP06-implementation-report.md`.
