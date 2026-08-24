# Integration synchronization

Capability execution is not synchronization. A compliant synchronization boundary requires durable runs, batches, cursors, idempotency keys, cancellation, retry, partial-failure accounting, and checkpoint commit only after safely persisted progress.

The current Jira adapter supports tested capability calls but not full or incremental delivery-data synchronization. The UI reports this limitation instead of displaying synthetic runs.
