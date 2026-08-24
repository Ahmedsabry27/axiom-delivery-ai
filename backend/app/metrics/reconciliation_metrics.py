from prometheus_client import Counter, Histogram

PARAMETER_RECONCILIATIONS = Counter(
    "parameter_reconciliation_total",
    "Deterministic parameter reconciliation outcomes",
    ["status"],
)
PARAMETER_RECONCILIATION_CONFLICTS = Counter(
    "parameter_reconciliation_conflicts_total",
    "Canonical parameter conflicts",
)
PARAMETER_RECONCILIATION_LATENCY = Histogram(
    "parameter_reconciliation_latency_seconds",
    "Deterministic parameter reconciliation latency",
)
