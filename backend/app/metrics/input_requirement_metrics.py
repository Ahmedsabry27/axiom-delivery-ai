from prometheus_client import Counter, Histogram

INPUT_REQUIREMENT_EVALUATIONS = Counter(
    "input_requirement_evaluations_total",
    "Input requirement evaluations",
    ["outcome", "schema_source"],
)
INPUT_REQUIREMENT_WAITS = Counter(
    "input_requirement_waits_total",
    "Runtime waits caused by unresolved required input",
)
INPUT_REQUIREMENT_MISSING_FIELDS = Counter(
    "input_requirement_missing_fields_total",
    "Required fields classified as missing, ambiguous, or invalid",
    ["reason"],
)
INPUT_REQUIREMENT_LATENCY = Histogram(
    "input_requirement_latency_seconds",
    "Deterministic input requirement evaluation latency",
)
