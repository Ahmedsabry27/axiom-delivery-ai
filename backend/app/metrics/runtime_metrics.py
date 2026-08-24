from prometheus_client import Counter, Gauge, Histogram

RUNTIME_EXECUTIONS = Counter(
    "runtime_executions_total",
    "Runtime execution lifecycle outcomes",
    ["status"],
)
RUNTIME_DURATION = Histogram(
    "runtime_execution_duration_seconds",
    "Terminal runtime execution duration",
)
RUNTIME_ACTIVE = Gauge(
    "runtime_active_executions",
    "Runtime executions actively owned by this process",
)
RUNTIME_STALE = Counter(
    "runtime_stale_executions_total",
    "Stale runtime executions selected for reconciliation",
)
RUNTIME_RECOVERIES = Counter(
    "runtime_recoveries_total",
    "Runtime executions reclaimed after ownership loss",
)
RUNTIME_RECOVERY_FAILURES = Counter(
    "runtime_recovery_failures_total",
    "Runtime executions terminalized during recovery",
    ["code"],
)
RUNTIME_LEASE_LOST = Counter(
    "runtime_lease_lost_total",
    "Local runtime workers fenced after losing ownership",
)
RUNTIME_EVENT_COUNTER_DRIFT_DETECTED = Counter(
    "runtime_event_counter_drift_detected_total",
    "Runtime event counters observed below their persisted event maximum",
)
RUNTIME_EVENT_COUNTER_RECONCILED = Counter(
    "runtime_event_counter_reconciled_total",
    "Runtime event counters atomically reconciled during append",
)
RUNTIME_EVENT_SEQUENCE_CONFLICT = Counter(
    "runtime_event_sequence_conflict_total",
    "Unique runtime event sequence conflicts detected",
)
RUNTIME_EVENT_APPEND_RETRY = Counter(
    "runtime_event_append_retry_total",
    "Canonical runtime event append retries after a sequence conflict",
)
RUNTIME_EVENT_APPEND_FAILURE = Counter(
    "runtime_event_append_failure_total",
    "Canonical runtime event append failures",
    ["reason"],
)
