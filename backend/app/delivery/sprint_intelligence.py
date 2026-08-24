from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median

HEALTH_WEIGHTS = {
    "delivery_progress": 0.25,
    "goal_confidence": 0.20,
    "blocked_work": 0.15,
    "scope_stability": 0.10,
    "dependency_health": 0.10,
    "backlog_readiness": 0.10,
    "quality": 0.10,
}
ANTI_PATTERN_THRESHOLDS = {
    "scope_injection_rate": 10,
    "aging_blocker_days": 3,
    "wip_items": 8,
    "qa_queue_items": 3,
    "readiness": 75,
    "carryover_rate": 20,
}


@dataclass(frozen=True, slots=True)
class Metric:
    value: float | None
    unit: str
    status: str
    sample_size: int
    completeness: float
    definition_version: str = "1.0"

    def to_dict(self):
        return asdict(self)


def _percent(
    numerator: float | None, denominator: float | None, direction="higher"
) -> Metric:
    if numerator is None or denominator is None or denominator <= 0:
        return Metric(None, "percent", "UNKNOWN", 0, 0)
    value = round(numerator / denominator * 100, 2)
    status = (
        ("GREEN" if value >= 85 else "AMBER" if value >= 70 else "RED")
        if direction == "higher"
        else ("GREEN" if value <= 10 else "AMBER" if value <= 25 else "RED")
    )
    return Metric(value, "percent", status, 1, 1)


def sprint_metrics(
    *,
    original_points: float | None,
    completed_original: float | None,
    completed_total: float | None,
    scope_added: float | None,
    scope_removed: float | None,
    blocked_points: float | None,
    active_points: float | None,
    blocker_ages: list[float],
    defects: int | None,
    completed_items: int | None,
) -> dict:
    gross = (
        None
        if original_points is None or scope_added is None or scope_removed is None
        else scope_added + scope_removed
    )
    defect = (
        None
        if defects is None or completed_items is None
        else _percent(defects, completed_items, "lower")
    )
    return {
        "predictability": _percent(completed_original, original_points).to_dict(),
        "commitment_achievement": _percent(completed_total, original_points).to_dict(),
        "carryover_rate": _percent(
            None
            if completed_original is None or original_points is None
            else max(original_points - completed_original, 0),
            original_points,
            "lower",
        ).to_dict(),
        "scope_change_rate": _percent(gross, original_points, "lower").to_dict(),
        "blocked_work_ratio": _percent(
            blocked_points, active_points, "lower"
        ).to_dict(),
        "average_blocker_age": Metric(
            round(sum(blocker_ages) / len(blocker_ages), 2) if blocker_ages else None,
            "days",
            "AMBER"
            if blocker_ages and sum(blocker_ages) / len(blocker_ages) >= 3
            else "GREEN"
            if blocker_ages
            else "UNKNOWN",
            len(blocker_ages),
            1 if blocker_ages else 0,
        ).to_dict(),
        "defect_rate": defect.to_dict()
        if defect
        else Metric(None, "defects_per_completed_item", "UNKNOWN", 0, 0).to_dict(),
    }


def sprint_health(dimensions: dict[str, float | None], minimum_dimensions=5) -> dict:
    available = {
        key: float(value)
        for key, value in dimensions.items()
        if key in HEALTH_WEIGHTS and value is not None
    }
    if len(available) < minimum_dimensions:
        return {
            "score": None,
            "status": "UNKNOWN",
            "dimensions": available,
            "completeness": round(len(available) / len(HEALTH_WEIGHTS), 2),
            "version": "1.0",
        }
    weight = sum(HEALTH_WEIGHTS[key] for key in available)
    score = round(
        sum(value * HEALTH_WEIGHTS[key] for key, value in available.items()) / weight, 2
    )
    return {
        "score": score,
        "status": "GREEN" if score >= 80 else "AMBER" if score >= 60 else "RED",
        "dimensions": available,
        "completeness": round(len(available) / len(HEALTH_WEIGHTS), 2),
        "version": "1.0",
    }


def forecast(
    *,
    completed: float | None,
    elapsed_days: int | None,
    total_days: int | None,
    historical_completed: list[float],
    original_points: float | None,
    blocked_points: float = 0,
    scope_added: float = 0,
) -> dict:
    if (
        completed is None
        or not elapsed_days
        or not total_days
        or original_points is None
        or original_points <= 0
    ):
        return {
            "completed_points": None,
            "carryover_points": None,
            "range": None,
            "goal_confidence": None,
            "method": "insufficient_data",
            "limitations": [
                "A positive original commitment, completed points, and sprint duration are required."
            ],
        }
    current_rate = completed / elapsed_days
    current_projection = current_rate * total_days
    historical = (
        median(historical_completed)
        if len(historical_completed) >= 3
        else current_projection
    )
    penalty = blocked_points * 0.35 + scope_added * 0.15
    projected = max(
        completed,
        min(
            original_points + scope_added,
            (current_projection * 0.6 + historical * 0.4) - penalty,
        ),
    )
    value = round(projected, 1)
    confidence = round(
        max(
            0,
            min(
                100,
                value / original_points * 100 - blocked_points / original_points * 20,
            ),
        ),
        0,
    )
    return {
        "completed_points": value,
        "carryover_points": round(max(original_points - value, 0), 1),
        "range": {
            "minimum": round(max(completed, value * 0.9), 1),
            "maximum": round(min(original_points + scope_added, value * 1.08), 1),
        },
        "goal_confidence": confidence,
        "method": "weighted observed throughput and historical median v1",
        "limitations": []
        if len(historical_completed) >= 3
        else [
            "Fewer than three historical sprints; current throughput has greater influence."
        ],
    }


def work_item_risk(
    *,
    blocked_days: int = 0,
    goal_critical=False,
    remaining_points: float = 0,
    days_remaining: int = 0,
    dependency=False,
    readiness_gaps: int = 0,
) -> dict:
    factors = {
        "blocked_age": min(blocked_days * 8, 32),
        "goal_critical": 25 if goal_critical else 0,
        "size_vs_time": 20 if remaining_points > days_remaining else 0,
        "dependency": 15 if dependency else 0,
        "readiness": min(readiness_gaps * 5, 10),
    }
    score = min(sum(factors.values()), 100)
    return {
        "score": score,
        "level": "CRITICAL"
        if score >= 75
        else "HIGH"
        if score >= 50
        else "MEDIUM"
        if score >= 25
        else "LOW",
        "factors": factors,
    }


def detect_anti_patterns(values: dict) -> list[dict]:
    rules = [
        ("scope-injection", "Mid-sprint scope injection", "scope_injection_rate", ">"),
        ("aging-blockers", "Aging blockers", "oldest_blocker_days", ">"),
        ("excessive-wip", "Excessive work in progress", "wip_items", ">"),
        ("qa-bottleneck", "QA queue bottleneck", "qa_queue_items", ">"),
        ("readiness-gap", "Backlog readiness gap", "readiness", "<"),
        ("recurring-carryover", "Recurring carryover", "carryover_rate", ">"),
    ]
    items = []
    for identifier, title, key, operator in rules:
        threshold = ANTI_PATTERN_THRESHOLDS[
            "aging_blocker_days" if key == "oldest_blocker_days" else key
        ]
        observed = values.get(key)
        matched = observed is not None and (
            observed > threshold if operator == ">" else observed < threshold
        )
        if matched:
            items.append(
                {
                    "id": identifier,
                    "title": title,
                    "severity": "HIGH"
                    if abs(observed - threshold) > threshold * 0.5
                    else "MEDIUM",
                    "observed": observed,
                    "threshold": f"{operator} {threshold}",
                    "recommendation": "Review the team system and working agreement; do not attribute performance to individuals.",
                }
            )
    return items
