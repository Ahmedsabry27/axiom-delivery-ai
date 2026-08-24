from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_HEALTH_WEIGHTS = {
    "project": 0.25,
    "release": 0.25,
    "risk": 0.20,
    "dependency": 0.15,
    "milestone": 0.15,
}


@dataclass(frozen=True, slots=True)
class ScoreResult:
    value: float | None
    status: str
    partial: bool
    factors: dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


def portfolio_health(
    components: dict[str, float | None],
    weights: dict[str, float] | None = None,
    minimum_components: int = 3,
) -> ScoreResult:
    selected = weights or DEFAULT_HEALTH_WEIGHTS
    if (
        set(selected) != set(DEFAULT_HEALTH_WEIGHTS)
        or abs(sum(selected.values()) - 1) > 0.0001
        or any(weight < 0 for weight in selected.values())
    ):
        raise ValueError(
            "Portfolio health weights must cover all components and total 1.0"
        )
    available = {
        key: float(components[key])
        for key in selected
        if components.get(key) is not None
    }
    if len(available) < minimum_components:
        return ScoreResult(None, "UNKNOWN", bool(available), available)
    available_weight = sum(selected[key] for key in available)
    value = round(
        sum(available[key] * selected[key] for key in available) / available_weight, 2
    )
    return ScoreResult(
        value,
        "GREEN" if value >= 80 else "AMBER" if value >= 60 else "RED",
        len(available) < len(selected),
        available,
    )


def sprint_predictability(
    committed_points: float | None,
    completed_points: float | None,
    committed_items: int | None = None,
    completed_items: int | None = None,
) -> ScoreResult:
    if committed_points and completed_points is not None:
        value, basis = (
            min(round(completed_points / committed_points * 100, 2), 100),
            "story_points",
        )
    elif committed_items and completed_items is not None:
        value, basis = (
            min(round(completed_items / committed_items * 100, 2), 100),
            "item_count",
        )
    else:
        return ScoreResult(None, "UNKNOWN", False, {})
    return ScoreResult(
        value,
        "GREEN" if value >= 85 else "AMBER" if value >= 70 else "RED",
        basis == "item_count",
        {"basis": 1.0},
    )


def attention_score(
    *, impact: int, urgency: int, critical_path: bool, age_periods: int
) -> ScoreResult:
    factors = {
        "impact": min(max(impact, 0), 5) * 7,
        "urgency": min(max(urgency, 0), 5) * 5,
        "critical_path": 25 if critical_path else 0,
        "age": min(max(age_periods, 0), 3) * 5,
    }
    value = float(min(sum(factors.values()), 100))
    return ScoreResult(
        value,
        "CRITICAL"
        if value >= 80
        else "HIGH"
        if value >= 60
        else "MEDIUM"
        if value >= 35
        else "LOW",
        False,
        factors,
    )
