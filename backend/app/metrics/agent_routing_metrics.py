from prometheus_client import Counter, Histogram

AGENT_ROUTING = Counter(
    "agent_routing_total",
    "Agent routing outcomes",
    ["selection_mode", "status", "domain"],
)
AGENT_ROUTING_RESOLVED = Counter(
    "agent_routing_resolved_total", "Resolved agent routes"
)
AGENT_ROUTING_UNAVAILABLE = Counter(
    "agent_routing_unavailable_total", "Unavailable agent routes"
)
AGENT_ROUTING_AMBIGUOUS = Counter(
    "agent_routing_ambiguous_total", "Ambiguous agent routes"
)
AGENT_ROUTING_INCOMPATIBLE = Counter(
    "agent_routing_incompatible_total", "Incompatible explicit agent routes"
)
AGENT_ROUTING_LATENCY = Histogram(
    "agent_routing_latency_seconds", "Agent routing latency"
)
