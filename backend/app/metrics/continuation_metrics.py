from prometheus_client import Counter, Histogram

CONTINUATION_RESPONSES = Counter(
    "continuation_responses_total", "Continuation responses", ["mode", "result"]
)
CONTINUATION_INTERPRETATION_FAILURES = Counter(
    "continuation_interpretation_failures_total",
    "Natural-language continuation interpretation failures",
)
CONTINUATION_ROUNDS = Counter(
    "continuation_rounds_total", "Continuation rounds", ["result"]
)
CONTINUATION_LATENCY = Histogram(
    "continuation_latency_seconds", "Continuation response processing latency"
)
