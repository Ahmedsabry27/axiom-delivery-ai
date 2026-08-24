# AX-FIX-01 outcome

## Completion decision

AX-FIX-01 INCOMPLETE — AX-EP07 REMAINS BLOCKED

The atomic runtime fix and all automated runtime gates pass. The required authenticated AX-EP07 browser journey remains red because the approver identity receives HTTP 403 when opening the newly submitted approval. Per the completion rules, the gate cannot be marked unblocked.

## Root cause and forward fix

The prior `next_event_sequence` allocator used next-value semantics and could disagree with durable history. The Jira reproduction also exposed a transaction boundary: `WAITING_FOR_INPUT` became visible before `required_input` was committed, allowing an in-memory SQLite fixture to tear down while the background task still appended. That produced a collision and an unobserved background exception.

Migration `a1c3e5f7b9d2`, directly after `f8d1b6c3e540`, adds non-null `last_event_sequence` with server default zero and backfills `MAX(sequence)` without assuming contiguity. Existing events and the unique constraint are preserved. All writers now allocate with atomic `UPDATE ... RETURNING`; the update and insert share the owning transaction on SQLite and PostgreSQL. `WAITING_FOR_INPUT`, the continuation, and `required_input` now commit together, and the tracker publishes afterward.

No broad workflow retry or swallowed `IntegrityError` was added. Database rollback is the conflict safeguard; retry/failure-handler expansion remains future work if production telemetry identifies a transient database error class that is safe and idempotent to retry.

## Tests and results

- Atomic/migration focused suite: 15 passed.
- Two-writer and six-writer coverage: passed.
- Twenty-writer SQLite contention: passed with sequences 1–20 and matching counter.
- Forced post-allocation failure: rollback leaves counter zero; next append receives one.
- State/event atomicity and post-commit tracker test: passed.
- Focused Jira case: 20 consecutive passes.
- Jira continuation module: 5 consecutive passes (7 tests each).
- Atomic runtime module: 10 consecutive passes (14 tests each).
- Backend quality: Ruff check and format check passed across 385 files; Python compilation passed.
- Backend full suite: 532 passed, then 532 passed again.
- Migration: clean upgrade and upgrade from `f8d1b6c3e540` passed; no-event backfill to zero and gapped sequences `(2, 7)` backfill to seven passed. FastAPI startup passed on the migrated disposable database.
- Frontend: ESLint, strict TypeScript, 33 test files / 105 tests, and production build passed.
- Browser negative-security journey: passed (self-approval, stale/expired approvals, unauthorized evidence, tenant isolation, and duplicate execution protections).
- Browser primary journey: failed at approver detail authorization (`GET /api/approvals/{id}` returned 403), so execution, verification, and refresh persistence were not reached.

## Files created

- `backend/alembic/versions/a1c3e5f7b9d2_atomic_runtime_event_sequence.py`
- `backend/tests/test_runtime_event_sequence_migration.py`
- `docs/runtime-event-sequence-concurrency.md`
- `docs/AX-FIX-01-outcome.md`

## Files modified

- `backend/app/models/runtime_execution.py`
- `backend/app/services/runtime_execution_service.py`
- `backend/tests/test_atomic_runtime_events.py`
- `backend/tests/test_input_requirements.py`

## Exact validation commands

```bash
cd backend
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
../.venv/bin/python -m compileall -q app tests
../.venv/bin/pytest -q
../.venv/bin/pytest -q

cd ../frontend
npm run validate
E2E_STATE_PATH=/private/tmp/ax_fix01_browser_clean_state.json \
VITE_API_URL=http://127.0.0.1:8011 \
npx playwright test -c playwright.live.config.ts \
e2e-live/action-center-live.spec.ts --project=live-1440
```

## Recommendation

Reassess AX-EP07 only after correcting or reseeding the approver authorization contract and rerunning the complete authenticated browser journey. The runtime sequence blocker itself is closed by automated evidence; the overall acceptance gate remains blocked by the mandatory browser failure.
