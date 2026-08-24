# AX-FIX-04 — Runtime Event Sequence Regression Outcome

## 1. Completion decision

`AX-FIX-04 COMPLETE — AX-EP10 GATE UNBLOCKED`

## 2. Exact failing test

`backend/tests/test_chat_runtime_continuation_path.py::test_real_chat_api_persists_and_projects_only_canonical_jira_create_fields[Create a JIRA ticket]`

## 3. Reproduction rate

The pre-fix full suite failed 1/1 at 538/539. The exact case passed 30/30 in isolation, confirming that the defect required suite load and transaction overlap.

## 4. Root cause

The application test database used in-memory SQLite with `StaticPool`. Background runtime writers and polling readers opened different SQLAlchemy sessions over the same physical connection. A reader rollback could undo a writer's counter update between allocation and event commit, leaving committed history ahead of `last_event_sequence`. AX-FIX-01's concurrency tests used file-backed SQLite and therefore did not exercise shared-connection transaction interference.

## 5. Conflicting event types

The failing stack was appending `parameter_reconciliation.completed`; the preceding canonical Jira pipeline event is `parameter_extraction.completed`. SQL parameters were intentionally hidden, so the original numeric duplicate was not exposed in logs. The deterministic regression reconstructs the invariant breach with counter 1, persisted maximum 3, and verifies allocation 4.

## 6. Counter versus maximum sequence

The failure class was `last_event_sequence < MAX(sequence)`, not two correctly committed atomic updates returning the same value. The production allocator now derives the next number atomically from the greater of both durable values.

## 7. Unsafe writer or fixture found

No second normal production constructor was found. Runtime lifecycle, continuation, recovery, cancellation, timeout, and failure paths use the canonical service. Historical migrations explicitly write historical sequences. The unsafe element was the shared-connection test fixture, which invalidated transaction isolation.

## 8. Allocation changes

One correlated `UPDATE ... RETURNING` assigns `max(last_event_sequence, MAX(persisted sequence)) + 1`. The insert follows in the same session and transaction.

## 9. Counter-drift handling

Safe reconciliation continues the append and emits structured warning fields and Prometheus counters without payload data. A read-only consistency checker reports counter, maximum, counts, duplicates, and consistency for one execution.

## 10. Bypass prevention

An architectural test scans application Python and permits `RuntimeExecutionEvent` construction only in `services/runtime_execution_service.py` (excluding the ORM declaration itself).

## 11. Fixture changes

Application API tests now use a process-specific file-backed SQLite database. A canonical test factory provides creation without events, creation with consistent history, canonical append, and immediate counter/max assertion.

## 12. Transaction behavior

Counter allocation and event insertion share a transaction. Existing transition and required-input atomicity remains unchanged. Tracker publication still occurs only after commit. Rollback and multi-session/concurrent tests pass.

## 13. Retry behavior

Only a specifically identified runtime sequence unique conflict is retryable. The transaction rolls back, a fresh session is opened, and canonical append is attempted once more. Other integrity errors fail immediately; a second collision is surfaced and counted.

## 14. Migration status

No schema change was required and no migration was created. Current head remains `b2d4f6a8c0e1`. FastAPI import passed with a disposable SQLite configuration.

## 15. Focused repeated results

- Exact failing case: 30/30 post-fix.
- Chat continuation file: 20/20 runs, 7/7 tests each.
- Jira continuation plus input requirements: 10/10 runs.
- Atomic and consistency modules: 10/10 runs.
- Initial combined focused gate: 28/28 tests.

## 16. Shuffled-order results

The installed pytest environment exposes no shuffle/random-order option or plugin. Order variation was therefore not runnable and is not reported as passed. Required explicit order/load coverage was supplied by the full suites and focused module combinations.

## 17. Full backend-suite results

Two consecutive suites passed: 546/546 in 163.29 seconds and 546/546 in 164.08 seconds. Log scans found no `IntegrityError`, unhandled background task, or async-cleanup signature.

## 18. Frontend-validation result

`npm run validate` passed: lint, strict TypeScript, 34 files / 110 tests, and mocks-disabled production build. AX-FIX-03 remains green.

## 19. Runtime-regression results

The full suites cover SSE ordering, continuation, approval continuation, required-input transitions, failure, cancellation, reconciliation, recovery, and atomic runtime events. The previously passed AX-EP07 authenticated browser journey was not repeated because this fix changes no browser/API contract and requires no migration.

## 20. Files created

- `backend/tests/runtime_event_factory.py`
- `backend/tests/test_runtime_event_counter_consistency.py`
- `docs/runtime-event-counter-consistency.md`
- `docs/AX-FIX-04-outcome.md`

## 21. Files modified

- `backend/app/metrics/runtime_metrics.py`
- `backend/app/services/runtime_execution_service.py`
- `backend/tests/conftest.py`
- `docs/runtime-event-sequence-concurrency.md`
- `docs/AX-EP10-outcome.md`

## 22. Remaining limitations

- The consistency checker is intentionally read-only; no bulk repair endpoint was added.
- Pytest order randomization is unavailable in the installed environment.
- SQLite validates local/test semantics; PostgreSQL remains the production row-serialization dialect.
- Existing Python/SQLAlchemy deprecation warnings remain unrelated to this fix.

## 23. Exact commands

```text
.venv/bin/pytest -q 'backend/tests/test_chat_runtime_continuation_path.py::test_real_chat_api_persists_and_projects_only_canonical_jira_create_fields[Create a JIRA ticket]'
.venv/bin/pytest -q backend/tests/test_chat_runtime_continuation_path.py
.venv/bin/pytest -q backend/tests/test_chat_runtime_continuation_path.py backend/tests/test_input_requirements.py
.venv/bin/pytest -q backend/tests/test_atomic_runtime_events.py backend/tests/test_runtime_event_counter_consistency.py
.venv/bin/pytest -q backend/tests
.venv/bin/pytest -q backend/tests
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m compileall -q backend/app backend/tests
cd backend && ../.venv/bin/alembic heads && cd ..
DATABASE_URL=sqlite+pysqlite:////private/tmp/ax_fix04_startup.db RUN_SCHEMA_CREATE=false PYTHONPATH=backend .venv/bin/python -c 'from app.main import app; print(app.title)'
cd frontend && npm run validate
```

The focused commands were looped to the repetition counts recorded above. `pytest --help` was inspected for randomization support.

## 24. Recommendation for restarting AX-EP10

Restart AX-EP10 from its prerequisite gate. Preserve the drift-safe allocator, file-backed multi-session test database, and direct-writer architectural guard.
