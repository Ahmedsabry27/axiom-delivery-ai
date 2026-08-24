from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

GRAPH_LIMITS = {
    "max_nodes": 5_000,
    "max_edges": 20_000,
    "max_depth": 8,
    "max_paths": 25,
    "default_visible_nodes": 200,
}

ENTITY_TYPES = {
    "PORTFOLIO",
    "PROGRAMME",
    "PROJECT",
    "TEAM",
    "SPRINT",
    "RELEASE",
    "MILESTONE",
    "EPIC",
    "WORK_ITEM",
    "DEFECT",
    "SYSTEM",
    "SERVICE",
    "ENVIRONMENT",
    "VENDOR",
    "EXTERNAL_PARTY",
}

RELATIONSHIP_TYPES = {
    "BLOCKS",
    "REQUIRES",
    "DELIVERS_TO",
    "DEPENDS_ON",
    "ENABLES",
    "PRECEDES",
    "SHARES_ENVIRONMENT",
    "SHARES_RESOURCE",
    "DATA_DEPENDENCY",
    "TECHNICAL_DEPENDENCY",
    "BUSINESS_DEPENDENCY",
    "APPROVAL_DEPENDENCY",
    "EXTERNAL_DEPENDENCY",
}

LIFECYCLE = {
    "IDENTIFIED": {"PROPOSED", "CANCELLED"},
    "PROPOSED": {"ACKNOWLEDGED", "CANCELLED"},
    "ACKNOWLEDGED": {"PLANNED", "CANCELLED"},
    "PLANNED": {"IN_PROGRESS", "AT_RISK", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"AT_RISK", "BLOCKED", "RESOLVED", "CANCELLED"},
    "AT_RISK": {"IN_PROGRESS", "BLOCKED", "ESCALATED", "RESOLVED"},
    "BLOCKED": {"IN_PROGRESS", "ESCALATED", "RESOLVED"},
    "ESCALATED": {"IN_PROGRESS", "BLOCKED", "RESOLVED"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
    # Existing records may use the pre-EP06 state.
    "OPEN": {"IN_PROGRESS", "AT_RISK", "BLOCKED", "RESOLVED", "CANCELLED"},
}

HEALTH_VERSION = "dependency-health-v1"
PRIORITY_VERSION = "dependency-priority-v1"


@dataclass(frozen=True)
class GraphEdge:
    dependency_id: str
    source: str
    target: str
    relationship_type: str = "DEPENDS_ON"
    status: str = "IDENTIFIED"
    critical: bool = False
    required_by: date | None = None
    forecast_resolution: date | None = None


class GraphLimitError(ValueError):
    pass


class DependencyGraph:
    """Deterministic directed graph. Core operations are O(V + E)."""

    def __init__(self, edges: Iterable[GraphEdge]):
        self.edges = list(edges)
        self.nodes = {
            node for edge in self.edges for node in (edge.source, edge.target)
        }
        if len(self.nodes) > GRAPH_LIMITS["max_nodes"]:
            raise GraphLimitError("Authorized graph exceeds the maximum node limit")
        if len(self.edges) > GRAPH_LIMITS["max_edges"]:
            raise GraphLimitError("Authorized graph exceeds the maximum edge limit")
        self.outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        self.incoming: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in self.edges:
            self.outgoing[edge.source].append(edge)
            self.incoming[edge.target].append(edge)

    def cycle_path(self, extra: GraphEdge | None = None) -> list[str]:
        outgoing = defaultdict(
            list, {key: list(value) for key, value in self.outgoing.items()}
        )
        nodes = set(self.nodes)
        if extra:
            outgoing[extra.source].append(extra)
            nodes.update((extra.source, extra.target))
        colour: dict[str, int] = {}
        parent: dict[str, str] = {}

        for start in sorted(nodes):
            if colour.get(start, 0) != 0:
                continue
            colour[start] = 1
            stack = [(start, iter(outgoing[start]))]
            while stack:
                node, edge_iterator = stack[-1]
                try:
                    target = next(edge_iterator).target
                except StopIteration:
                    colour[node] = 2
                    stack.pop()
                    continue
                if colour.get(target, 0) == 0:
                    parent[target] = node
                    colour[target] = 1
                    stack.append((target, iter(outgoing[target])))
                elif colour.get(target) == 1:
                    path = [node]
                    while path[-1] != target:
                        path.append(parent[path[-1]])
                    return [*reversed(path), target]
        return []

    def topological_order(self) -> list[str]:
        indegree = {node: len(self.incoming[node]) for node in self.nodes}
        queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while queue:
            node = queue.popleft()
            ordered.append(node)
            for edge in self.outgoing[node]:
                indegree[edge.target] -= 1
                if indegree[edge.target] == 0:
                    queue.append(edge.target)
        if len(ordered) != len(self.nodes):
            raise ValueError("Graph contains a cycle")
        return ordered

    def traverse(self, start: str, *, direction: str, depth: int = 3) -> dict[str, Any]:
        if depth < 1 or depth > GRAPH_LIMITS["max_depth"]:
            raise GraphLimitError("Traversal depth is outside the permitted range")
        adjacency = self.outgoing if direction == "downstream" else self.incoming
        queue = deque([(start, 0)])
        visited = {start}
        nodes: list[dict[str, Any]] = []
        edges: list[GraphEdge] = []
        while queue:
            node, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for edge in adjacency[node]:
                next_node = edge.target if direction == "downstream" else edge.source
                edges.append(edge)
                if next_node not in visited:
                    visited.add(next_node)
                    nodes.append({"id": next_node, "depth": current_depth + 1})
                    queue.append((next_node, current_depth + 1))
        return {
            "nodes": nodes,
            "edges": edges,
            "maxDepth": max((n["depth"] for n in nodes), default=0),
        }

    def paths(
        self, source: str, target: str, *, max_paths: int = 10, max_depth: int = 8
    ) -> list[list[GraphEdge]]:
        max_paths = min(max(max_paths, 1), GRAPH_LIMITS["max_paths"])
        if max_depth < 1 or max_depth > GRAPH_LIMITS["max_depth"]:
            raise GraphLimitError("Path depth is outside the permitted range")
        results: list[list[GraphEdge]] = []
        stack: list[tuple[str, list[GraphEdge], set[str]]] = [(source, [], {source})]
        while stack and len(results) < max_paths:
            node, path, seen = stack.pop()
            if len(path) >= max_depth:
                continue
            for edge in reversed(self.outgoing[node]):
                if edge.target in seen:
                    continue
                next_path = [*path, edge]
                if edge.target == target:
                    results.append(next_path)
                    if len(results) >= max_paths:
                        break
                else:
                    stack.append((edge.target, next_path, {*seen, edge.target}))
        return results

    def critical_paths(self) -> list[dict[str, Any]]:
        cycle = self.cycle_path()
        if cycle:
            return [
                {
                    "classification": "INSUFFICIENT_DATA",
                    "nodes": cycle,
                    "limitations": ["Critical paths require an acyclic graph."],
                }
            ]
        ordered = self.topological_order()
        distance = {node: 0 for node in ordered}
        predecessor: dict[str, GraphEdge] = {}
        for node in ordered:
            for edge in self.outgoing[node]:
                if distance[node] + 1 > distance[edge.target]:
                    distance[edge.target] = distance[node] + 1
                    predecessor[edge.target] = edge
        if not distance:
            return []
        end = max(distance, key=distance.get)
        path: list[GraphEdge] = []
        cursor = end
        while cursor in predecessor:
            edge = predecessor[cursor]
            path.append(edge)
            cursor = edge.source
        path.reverse()
        if not path:
            return []
        complete_dates = all(
            edge.required_by and edge.forecast_resolution for edge in path
        )
        delay = sum(
            max((edge.forecast_resolution - edge.required_by).days, 0)
            for edge in path
            if edge.required_by and edge.forecast_resolution
        )
        classification = (
            "CALCULATED_CRITICAL_PATH" if complete_dates else "POTENTIAL_CRITICAL_PATH"
        )
        return [
            {
                "id": "CP-001",
                "classification": classification,
                "nodes": [path[0].source, *[edge.target for edge in path]],
                "dependencies": [edge.dependency_id for edge in path],
                "pathLength": len(path),
                "currentDelayDays": delay,
                "dataCompleteness": round(
                    sum(
                        bool(edge.required_by and edge.forecast_resolution)
                        for edge in path
                    )
                    / len(path),
                    2,
                ),
                "limitations": []
                if complete_dates
                else [
                    "Formal duration and float require complete required-by and forecast dates."
                ],
            }
        ]

    def bottlenecks(self) -> list[dict[str, Any]]:
        findings = []
        for node in self.nodes:
            fan_in, fan_out = len(self.incoming[node]), len(self.outgoing[node])
            impacted = [
                edge
                for edge in self.outgoing[node]
                if edge.status in {"AT_RISK", "BLOCKED", "ESCALATED"} or edge.critical
            ]
            if max(fan_in, fan_out) >= 2 and impacted:
                findings.append(
                    {
                        "node": node,
                        "fanIn": fan_in,
                        "fanOut": fan_out,
                        "priority": "HIGH" if max(fan_in, fan_out) >= 3 else "MEDIUM",
                        "basis": f"{fan_in} incoming and {fan_out} outgoing relationships with {len(impacted)} delivery-impact signal(s).",
                        "affectedDependencies": [
                            edge.dependency_id for edge in impacted
                        ],
                        "limitations": [
                            "Connectivity is reported only where status or criticality supplies delivery-impact evidence."
                        ],
                    }
                )
        return sorted(
            findings, key=lambda item: item["fanIn"] + item["fanOut"], reverse=True
        )


def validate_transition(
    current: str, requested: str, reason: str | None = None
) -> None:
    if requested not in LIFECYCLE.get(current, set()):
        raise ValueError(f"Invalid dependency transition: {current} → {requested}")
    if requested == "ESCALATED" and not reason:
        raise ValueError("Escalation requires a reason")
    if requested == "CLOSED" and not reason:
        raise ValueError("Closure requires a note")


def dependency_health(
    dependency: Any,
    *,
    evidence_count: int,
    downstream_count: int,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    required = {
        "owner": bool(dependency.owner_id or dependency.provider_owner_id),
        "requiredByDate": bool(dependency.required_by_date),
        "status": bool(dependency.status),
    }
    completeness = sum(required.values()) / len(required)
    limitations = [
        f"Missing {key}." for key, present in required.items() if not present
    ]
    dimensions = {
        "scheduleAlignment": 25,
        "statusAndProgress": 20,
        "ownershipAndAcknowledgement": 15,
        "evidenceFreshness": 10,
        "downstreamImpact": 15,
        "resolutionConfidence": 10,
        "reviewHygiene": 5,
    }
    if completeness < 1:
        return {
            "score": None,
            "status": "UNKNOWN",
            "dimensions": dimensions,
            "calculatedAt": datetime.now(UTC).isoformat(),
            "dataCompleteness": round(completeness, 2),
            "limitations": limitations,
            "definitionVersion": HEALTH_VERSION,
        }
    score = 100
    if (
        dependency.forecast_resolution_date
        and dependency.forecast_resolution_date > dependency.required_by_date
    ):
        score -= 25
    elif dependency.required_by_date < today and dependency.status not in {
        "RESOLVED",
        "CLOSED",
    }:
        score -= 25
    if dependency.status in {"BLOCKED", "ESCALATED"}:
        score -= 20
    elif dependency.status == "AT_RISK":
        score -= 12
    if not dependency.acknowledged_at:
        score -= 15
    if evidence_count == 0:
        score -= 10
    if downstream_count >= 3:
        score -= 15
    elif downstream_count:
        score -= 5
    if not dependency.forecast_resolution_date:
        score -= 10
    reviewed_at = dependency.last_reviewed_at
    if reviewed_at and reviewed_at.tzinfo is None:
        reviewed_at = reviewed_at.replace(tzinfo=UTC)
    if not reviewed_at or reviewed_at < datetime.now(UTC) - timedelta(days=14):
        score -= 5
    score = max(score, 0)
    status = "GREEN" if score >= 80 else "AMBER" if score >= 60 else "RED"
    return {
        "score": score,
        "status": status,
        "dimensions": dimensions,
        "calculatedAt": datetime.now(UTC).isoformat(),
        "dataCompleteness": 1.0,
        "limitations": limitations,
        "definitionVersion": HEALTH_VERSION,
    }


def dependency_priority(
    dependency: Any,
    *,
    downstream_nodes: list[str],
    evidence_count: int,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    score = 0
    factors: list[dict[str, Any]] = []

    def add(name: str, points: int) -> None:
        nonlocal score
        score += points
        factors.append({"factor": name, "points": points})

    if dependency.critical_path:
        add("Critical-path dependency", 30)
    if (
        dependency.forecast_resolution_date
        and dependency.required_by_date
        and dependency.forecast_resolution_date > dependency.required_by_date
    ):
        add("Forecast resolution after required date", 25)
    if dependency.status == "BLOCKED":
        add("Currently blocked", 25)
    node_types = {node.split(":", 1)[0] for node in downstream_nodes}
    if "RELEASE" in node_types:
        add("Release impact", 20)
    if "MILESTONE" in node_types:
        add("Milestone impact", 20)
    if "SPRINT" in node_types or "WORK_ITEM" in node_types:
        add("Sprint delivery impact", 15)
    if len(downstream_nodes) > 1:
        add("Multiple downstream consumers", 15)
    if not dependency.acknowledged_at:
        add("No acknowledged provider", 15)
    if not dependency.owner_id:
        add("Missing owner", 15)
    if dependency.identified_at.date() < today - timedelta(
        days=30
    ) and dependency.status not in {"RESOLVED", "CLOSED", "CANCELLED"}:
        add("Aging beyond threshold", 10)
    if not dependency.committed_resolution_date:
        add("No committed resolution date", 10)
    if evidence_count == 0:
        add("No authorized evidence", 5)
    if dependency.external:
        add("External dependency", 5)
    if dependency.status == "ESCALATED":
        add("Escalated", 5)
    band = (
        "CRITICAL"
        if score >= 70
        else "HIGH"
        if score >= 45
        else "MEDIUM"
        if score >= 20
        else "LOW"
    )
    return {
        "score": score,
        "band": band,
        "triggeredFactors": factors,
        "affectedEntities": downstream_nodes,
        "calculatedAt": datetime.now(UTC).isoformat(),
        "ruleVersion": PRIORITY_VERSION,
    }


def impact_result(
    graph: DependencyGraph, edge: GraphEdge, *, slip_days: int, depth: int = 5
) -> dict[str, Any]:
    traversal = graph.traverse(edge.target, direction="downstream", depth=depth)
    direct = [item["id"] for item in traversal["nodes"] if item["depth"] == 1]
    indirect = [item["id"] for item in traversal["nodes"] if item["depth"] > 1]
    all_nodes = [edge.target, *direct, *indirect]
    grouped: dict[str, list[str]] = defaultdict(list)
    for node in all_nodes:
        entity_type, entity_id = node.split(":", 1)
        grouped[entity_type].append(entity_id)
    return {
        "directlyAffectedEntities": direct,
        "indirectlyAffectedEntities": indirect,
        "affectedWorkItems": grouped["WORK_ITEM"],
        "affectedSprints": grouped["SPRINT"],
        "affectedMilestones": grouped["MILESTONE"],
        "affectedReleases": grouped["RELEASE"],
        "affectedTeams": grouped["TEAM"],
        "maximumDownstreamDepth": traversal["maxDepth"],
        "estimatedDelayRange": {"minimumDays": 0, "maximumDays": slip_days},
        "confidence": 0.8
        if all(edge_item.required_by for edge_item in traversal["edges"])
        else 0.6,
        "assumptions": [
            "Delay is propagated as a bounded exposure range; authoritative dates are unchanged."
        ],
        "limitations": [
            "No duration is invented for downstream entities lacking explicit timing data."
        ],
        "readOnly": True,
    }
