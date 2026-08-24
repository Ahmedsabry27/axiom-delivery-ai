from prometheus_client import Counter, Histogram

CAPABILITY_RESOLUTIONS = Counter(
    "capability_resolution_total",
    "Capability resolution outcomes",
    ["domain", "operation", "status", "capability_type"],
)
CAPABILITY_RESOLUTION_LATENCY = Histogram(
    "capability_resolution_latency_seconds",
    "Capability resolution latency",
)
CAPABILITY_RESOLUTION_UNAVAILABLE = Counter(
    "capability_resolution_unavailable_total", "Unavailable capability resolutions"
)
CAPABILITY_RESOLUTION_AMBIGUOUS = Counter(
    "capability_resolution_ambiguous_total", "Ambiguous capability resolutions"
)
CAPABILITY_RESOLUTION_UNAUTHORIZED = Counter(
    "capability_resolution_unauthorized_total", "Unauthorized capability resolutions"
)
CAPABILITY_RESOLUTION_UNHEALTHY = Counter(
    "capability_resolution_unhealthy_total", "Unhealthy capability resolutions"
)
