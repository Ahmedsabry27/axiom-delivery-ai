from prometheus_client import Counter, Histogram

INTENT_ANALYSIS_REQUESTS = Counter(
    "intent_analysis_requests_total",
    "Structured intent analysis attempts",
    ["provider", "status"],
)
INTENT_ANALYSIS_FAILURES = Counter(
    "intent_analysis_failures_total",
    "Structured intent analysis failures",
    ["provider", "code"],
)
INTENT_ANALYSIS_AMBIGUOUS = Counter(
    "intent_analysis_ambiguous_total",
    "Structured intent analyses marked ambiguous",
    ["provider"],
)
INTENT_ANALYSIS_LATENCY = Histogram(
    "intent_analysis_latency_seconds",
    "Structured intent analysis latency",
    ["provider"],
)
