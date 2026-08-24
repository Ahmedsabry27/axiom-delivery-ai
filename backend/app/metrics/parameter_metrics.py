from prometheus_client import Counter, Histogram

PARAMETER_EXTRACTION_REQUESTS = Counter(
    "parameter_extraction_requests_total",
    "Structured parameter extraction attempts",
    ["provider", "status"],
)
PARAMETER_EXTRACTION_FAILURES = Counter(
    "parameter_extraction_failures_total",
    "Structured parameter extraction failures",
    ["provider", "code"],
)
PARAMETER_EXTRACTION_LATENCY = Histogram(
    "parameter_extraction_latency_seconds",
    "Structured parameter extraction latency",
    ["provider"],
)
PARAMETER_EXTRACTION_PARAMETERS = Counter(
    "parameter_extraction_parameters_total",
    "Number of parameters returned by successful extraction",
    ["provider"],
)
