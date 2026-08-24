from prometheus_client import Counter, Histogram

PLANNING_REQUESTS = Counter(
    "planning_requests_total",
    "Planning requests",
    ["domain", "capability_type", "outcome"],
)
PLANNING_FAILURES = Counter("planning_failures_total", "Planning failures", ["reason"])
PLANNING_LATENCY = Histogram("planning_latency_seconds", "Planning latency")
PLANNING_TASKS = Counter(
    "planning_tasks_total",
    "Tasks produced by deterministic planning",
    ["capability_type"],
)
