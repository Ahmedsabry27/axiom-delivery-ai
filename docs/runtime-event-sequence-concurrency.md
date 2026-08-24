# Runtime event sequence concurrency

Runtime events are canonically ordered per execution by `sequence ASC`. Timestamps are informational. Historical gaps are allowed, but every newly committed append is unique and strictly increasing.

`runtime_executions.last_event_sequence` is at least the highest sequence allocated by a committed append. It starts at zero. Every writer uses one database statement that also self-heals pre-existing drift:

```sql
UPDATE runtime_executions
SET last_event_sequence = CASE
  WHEN last_event_sequence < (
    SELECT COALESCE(MAX(sequence), 0)
    FROM runtime_execution_events
    WHERE execution_id = runtime_executions.id
  )
  THEN (
    SELECT COALESCE(MAX(sequence), 0) + 1
    FROM runtime_execution_events
    WHERE execution_id = runtime_executions.id
  )
  ELSE last_event_sequence + 1
END
WHERE id = :execution_id
RETURNING last_event_sequence;
```

The counter update and event insert use the same SQLAlchemy transaction. A rollback therefore restores both. PostgreSQL serializes the row update; installed SQLite supports the same atomic `UPDATE ... RETURNING` behavior even though `SELECT FOR UPDATE` is ignored. Application tests use file-backed SQLite so separate sessions never share a physical connection transaction. The existing `(execution_id, sequence)` unique constraint remains a final invariant guard.

```text
Writer A ─┐
          ├─► Atomic database counter ─► unique sequence ─► event insert ─► commit
Writer B ─┘
```

Lifecycle transitions call the same append primitive inside their state transaction. In particular, `WAITING_FOR_INPUT`, its continuation, and `required_input` event commit together. Downstream tracker publication occurs only after commit. The additive migration `a1c3e5f7b9d2` backfills the counter from each execution's actual maximum event sequence, or zero when it has no events; it does not repair or remove historical gaps.

The deprecated `next_event_sequence` column is retained for schema compatibility but is no longer used by writers. A future compatibility migration may remove it after all deployed versions understand `last_event_sequence`.

AX-FIX-04 adds safe drift logging and metrics, a read-only per-execution consistency check, one narrowly classified retry after rollback, a canonical test factory, and an architectural test that prevents new production constructors outside the canonical service. See `docs/runtime-event-counter-consistency.md`.
