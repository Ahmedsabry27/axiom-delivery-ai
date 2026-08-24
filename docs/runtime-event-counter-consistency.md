# Runtime event counter consistency

For every execution, the durable invariant is:

```text
last_event_sequence >= MAX(runtime_execution_events.sequence)
```

Normal runtime code constructs and persists `RuntimeExecutionEvent` only in `RuntimeExecutionService._append_runtime_event_locked`. Lifecycle transitions and recovery call that same primitive. An architectural regression test scans production code and fails if another constructor appears.

## Drift-safe allocation

The allocator performs one correlated database update equivalent to:

```sql
last_event_sequence =
  CASE
    WHEN last_event_sequence < MAX(persisted sequence)
      THEN MAX(persisted sequence) + 1
    ELSE last_event_sequence + 1
  END
```

The update and insert remain in the owning transaction. PostgreSQL serializes the execution-row update. File-backed SQLite serializes writes while allowing independent sessions to retain independent transaction boundaries. A rollback reverts both the counter and event.

Drift reconciliation logs only the execution ID, event type, stored counter, observed maximum, allocated sequence, dialect, and status. It increments dedicated Prometheus counters. Event payloads, prompts, credentials, and tokens are never logged.

## Conflict handling

The public append method recognizes only the named/runtime-event sequence uniqueness failure. It rolls back, opens a fresh transaction, and retries once through the canonical allocator. Other integrity errors fail immediately. A second sequence conflict fails normally; it is never ignored and does not recursively append a failure event.

## Consistency inspection

`check_execution_event_sequence` is a read-only, single-execution administrative/test primitive. It reports the counter, maximum sequence, event count, duplicate count, and consistency without changing or deleting history. No global repair runs on requests.

## Test database

Application-level tests use a process-specific file-backed SQLite database. The earlier in-memory `StaticPool` gave multiple SQLAlchemy sessions one physical connection, allowing a polling session's rollback to interfere with a background writer's transaction. Dedicated connections now provide meaningful multi-session behavior.

Historical-import migrations remain the only explicit-sequence writers. They reconcile their historical counter through migration backfill and are not callable by normal runtime paths.
