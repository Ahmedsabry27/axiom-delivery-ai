# AX-PRR-01 Validation Evidence

## Repository baseline

- `git branch --show-current` → `main`.
- `git rev-parse HEAD` → failed: unknown revision.
- `git log -1 --oneline` → failed: branch has no commits.
- `git status --short` → all repository paths untracked.

## Commands and results

| Command | Result |
|---|---|
| `find . -path './frontend/node_modules' -prune -o -name AGENTS.md -print` | No applicable project AGENTS.md found outside dependency content |
| `npm ci` (frontend) | Passed; 903 packages installed |
| `VITE_USE_MOCK_DELIVERY_DATA=false npm run validate` | Failed deterministically at strict TypeScript; tests/build not reached |
| `../.venv/bin/pytest -q` (backend run 1) | 578 passed, 388 warnings, 183.31 s |
| `../.venv/bin/pytest -q` (backend run 2) | 578 passed, 388 warnings, 246.27 s |
| 10× `pytest -q tests/test_atomic_runtime_events.py tests/test_chat_runtime_continuation_path.py tests/test_action_center.py tests/test_budget_enforcement.py` | All 10 passed; 47 tests per run, 470 repeated test executions |
| `../.venv/bin/ruff check app tests` | Passed |
| `../.venv/bin/ruff format --check app tests` | Passed; 397 files formatted |
| `../.venv/bin/alembic heads` | One head: `d4f6a8b0c2e5` |
| clean SQLite `alembic upgrade head` and `alembic current` | Passed; current `d4f6a8b0c2e5` |
| `APP_ENV=production ../.venv/bin/python -c 'import app.core.config'` | Failed closed: `RUN_SCHEMA_CREATE is forbidden in production` (inherited env); expected safe behavior |
| `gitleaks detect --no-git --source . --redact --no-banner --report-format json` | Passed; no leaks found in ~16.48 MB |
| `npm audit --omit=dev --json` | Not verified: `ENOTFOUND registry.npmjs.org` |
| `command -v pip-audit` | Not installed; Python dependency audit not verified |
| `git diff --check` | Passed, but repository is untracked so this is weak evidence |

## Frontend failure

`src/pages/portfolio/PortfolioPages.tsx` reports TS2604/TS2786: `Icon` cannot be used as a JSX component because inferred tuple type includes `string | number`. The mandatory frontend chain stopped at this product failure. Required three repeated passes, production build, and browser execution are not passed.

## Browser evidence

Static inventory found live specs for delivery, RAID, dependency, actions, meetings, governance, agents, and AX-EP10. No Portfolio live spec was found. Mocked release specs do not establish production behavior. The latest AX-EP10 completion run immediately before this audit failed because execution status was `FAILED` rather than `COMPLETED`.

Executed authenticated browser journeys in this audit: 0. Responsive runs: 0. Negative-security browser runs: 0. These are failed release gates, not passes.

Total backend test executions counted by pytest across the two complete runs and ten focused repetitions: 1,626 passed. This is repetition evidence, not 1,626 unique tests.

## Mandatory validations not executed or not passed

- Frontend full validation three times: failed on first run.
- Frontend shuffled seeds: not run.
- Production build with mocks disabled: not reached.
- Fully configured FastAPI startup: not run; fail-closed configuration import verified.
- Authenticated persisted Playwright desktop/tablet/mobile: not run.
- npm dependency audit: environmental DNS failure.
- Python dependency audit: tool unavailable.
- External backup/restore/deployment/rollback evidence: not available.
