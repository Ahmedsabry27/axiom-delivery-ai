# AX-EP07 Outcome — Approval and Action Center

## Phase A findings

AX-EP01 through AX-EP06 were present and their prerequisite gates were green. The repository already had tenant-scoped `ProposedAction`, evidence joins, append-only audit and a durable tool-governance `ApprovalRequest`. It did not have delivery-action policy classification, approval binding to action versions, immutable human decisions, execution attempts, verification, notifications, action/approval workbenches or cross-module approval attention.

No P0 prerequisite blocker was found. Baseline gates were 522 backend tests and 77 frontend tests. Migration head before this epic was `e7c0a5f2b438`.

## Delivered

- Extended durable proposed actions and linked governance approvals.
- Added immutable approval decisions, versioned policy definitions, idempotent executions, independent verifications and actionable notifications.
- Added deterministic fail-closed policy and explicit internal RAID adapter allowlist.
- Added tenant isolation, separation of duties, payload/version binding, expiry, optimistic edit concurrency, execution row locking and replay protection.
- Added `/actions`, `/approvals`, policy and notification APIs; retained the legacy catalogue at `/api/action-catalog`.
- Replaced the Actions catalogue UI and Approvals placeholder with responsive, URL-addressable workbenches and safe partial-data states.
- Integrated RAID, Dependency Intelligence, Copilot, My Day, Command Center and append-only audit.
- Added migration `f8d1b6c3e540` plus backend, frontend and live-browser coverage.

## Validation evidence

- Ruff: pass across `backend`.
- Migration: fresh upgrade, downgrade to `e7c0a5f2b438`, and re-upgrade pass on disposable SQLite.
- Backend focused security/action tests: pass.
- Backend full suite: final clean rerun passed 529 tests. An earlier run exposed only the intentionally expanded seed-state contract; after updating that assertion, the entire suite passed.
- Frontend validation: 26 files / 80 tests pass; ESLint, TypeScript and production build pass. The one parallel-run timeout in an unchanged dependency test disappeared on the required serial full rerun.
- Live seed: signed requester, approver, executor, verifier and cross-tenant identities generated against a disposable migrated database.
- Authenticated Playwright implementation: `frontend/e2e-live/action-center-live.spec.ts` covers requester creation/submission, approver rationale, exactly-once execution, independent verification, reload persistence, audit trace and negative controls.

## Final acceptance after AX-FIX-01 and AX-FIX-02

The runtime sequencing and approval-detail blockers are closed. Runtime events now use the authoritative transactional `last_event_sequence` allocator, and approval list/detail/decision authorization shares one tenant-scoped policy. The signed browser identity transition was corrected without changing production authentication.

Final acceptance evidence:

- Ruff, formatting, and Python compilation passed.
- Full backend suite passed twice consecutively: 534 tests on each run.
- Focused approval, atomic-runtime, and Jira-continuation regression: 30 passed.
- Frontend lint, strict TypeScript, 33 files / 106 tests, and mocks-disabled production build passed.
- Clean migration to `a1c3e5f7b9d2` and FastAPI startup passed on a disposable SQLite database.
- The authenticated requester → approver → executor → verifier journey passed, including immutable decision, exactly-once execution, verification, audit, and reload persistence.
- Negative browser controls passed for self-approval, stale/expired approval, missing evidence, cross-tenant access, and duplicate execution.

The reproducible browser command is:

```bash
cd backend
DATABASE_URL=sqlite:////private/tmp/ax_fix02_browser.sqlite \
APP_ENV=e2e E2E_AUTH_ENABLED=true \
E2E_AUTH_SECRET=axiom-fix02-browser-proof-secret-2026 \
E2E_AUTH_MAX_LIFETIME_SECONDS=7200 \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011

cd ../frontend
E2E_STATE_PATH=/private/tmp/ax_fix02_browser_state.json \
VITE_API_URL=http://127.0.0.1:8011 \
npx playwright test -c playwright.live.config.ts e2e-live/action-center-live.spec.ts \
--project=live-1440
```

No external Jira, Azure DevOps, messaging, email, calendar or workflow action was executed.

AX-EP07 COMPLETE
