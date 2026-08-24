from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    CONTEXTUAL = "CONTEXTUAL"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    key: str
    name: str
    description: str
    formula: str
    unit: str
    direction: MetricDirection
    green_threshold: float | None
    amber_threshold: float | None
    red_threshold: float | None
    minimum_sample_size: int
    missing_data_behaviour: str
    applicable_entity_types: tuple[str, ...]
    version: str = "1.0"


def _metric(
    key: str,
    name: str,
    formula: str,
    unit: str,
    direction: MetricDirection,
    entities: tuple[str, ...],
    green: float | None = None,
    amber: float | None = None,
    red: float | None = None,
    description: str = "",
) -> MetricDefinition:
    return MetricDefinition(
        key,
        name,
        description or name,
        formula,
        unit,
        direction,
        green,
        amber,
        red,
        1,
        "UNKNOWN",
        entities,
    )


METRIC_DEFINITIONS = (
    _metric(
        "portfolio_health",
        "Portfolio Health",
        "Weighted composite: project 30%, release 25%, risk 20%, dependency 15%, milestone 10%",
        "percent",
        MetricDirection.HIGHER_IS_BETTER,
        ("Portfolio",),
        80,
        60,
        0,
    ),
    _metric(
        "sprint_predictability",
        "Sprint Predictability",
        "Completed originally committed scope / originally committed scope * 100",
        "percent",
        MetricDirection.HIGHER_IS_BETTER,
        ("Sprint",),
        85,
        70,
        0,
    ),
    _metric(
        "commitment_achievement",
        "Commitment Achievement",
        "Completed committed work / committed work * 100",
        "percent",
        MetricDirection.HIGHER_IS_BETTER,
        ("Sprint", "Release"),
        85,
        70,
        0,
    ),
    _metric(
        "velocity",
        "Velocity",
        "Completed story points per sprint",
        "story_points",
        MetricDirection.CONTEXTUAL,
        ("Sprint",),
    ),
    _metric(
        "carryover_rate",
        "Carryover Rate",
        "Incomplete originally committed work / originally committed work * 100",
        "percent",
        MetricDirection.LOWER_IS_BETTER,
        ("Sprint",),
        10,
        25,
        100,
    ),
    _metric(
        "cycle_time",
        "Cycle Time",
        "Work completed timestamp - work started timestamp",
        "days",
        MetricDirection.LOWER_IS_BETTER,
        ("WorkItem",),
    ),
    _metric(
        "lead_time",
        "Lead Time",
        "Work completed timestamp - work created timestamp",
        "days",
        MetricDirection.LOWER_IS_BETTER,
        ("WorkItem",),
    ),
    _metric(
        "blocked_work_ratio",
        "Blocked Work Ratio",
        "Blocked active work / total active work * 100",
        "percent",
        MetricDirection.LOWER_IS_BETTER,
        ("Project", "Sprint"),
        5,
        15,
        100,
    ),
    _metric(
        "average_blocker_age",
        "Average Blocker Age",
        "Total age of active blockers / active blocker count",
        "days",
        MetricDirection.LOWER_IS_BETTER,
        ("Project", "Sprint"),
    ),
    _metric(
        "backlog_readiness",
        "Backlog Readiness",
        "Items meeting configured readiness dimensions / assessed items * 100",
        "percent",
        MetricDirection.HIGHER_IS_BETTER,
        ("Project", "Sprint"),
        85,
        70,
        0,
    ),
    _metric(
        "defect_rate",
        "Defect Rate",
        "Defects / configured denominator (work items, release, or story points)",
        "ratio",
        MetricDirection.LOWER_IS_BETTER,
        ("Project", "Sprint", "Release"),
    ),
    _metric(
        "escaped_defect_rate",
        "Escaped Defect Rate",
        "Production defects / total defects * 100",
        "percent",
        MetricDirection.LOWER_IS_BETTER,
        ("Project", "Release"),
        2,
        8,
        100,
    ),
    _metric(
        "dependency_age",
        "Dependency Age",
        "Current date - dependency identified or blocked date",
        "days",
        MetricDirection.LOWER_IS_BETTER,
        ("RAIDItem",),
    ),
    _metric(
        "risk_exposure",
        "Risk Exposure",
        "Probability score * impact score",
        "score",
        MetricDirection.LOWER_IS_BETTER,
        ("RAIDItem",),
        5,
        12,
        25,
    ),
    _metric(
        "release_readiness",
        "Release Readiness",
        "Configured completion across code, SIT, UAT, regression, performance, security, CAB, approval, rollback, monitoring and support dimensions",
        "percent",
        MetricDirection.HIGHER_IS_BETTER,
        ("Release",),
        85,
        70,
        0,
    ),
)


def safe_percentage(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def sprint_predictability(
    completed_committed: float | None, originally_committed: float | None
) -> float | None:
    return safe_percentage(completed_committed, originally_committed)


def commitment_achievement(
    completed: float | None, committed: float | None
) -> float | None:
    return safe_percentage(completed, committed)


def carryover_rate(
    incomplete_committed: float | None, originally_committed: float | None
) -> float | None:
    return safe_percentage(incomplete_committed, originally_committed)


def risk_exposure(
    probability_score: float | None, impact_score: float | None
) -> float | None:
    if probability_score is None or impact_score is None:
        return None
    return probability_score * impact_score


def metric_catalogue() -> list[dict]:
    return [asdict(definition) for definition in METRIC_DEFINITIONS]
