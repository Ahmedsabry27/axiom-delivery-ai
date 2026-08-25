from app.agile_intelligence.service import (
    ANONYMOUS_TEAM_HEALTH_MINIMUM,
    aggregate_team_health,
    percentile,
    safe_ratio,
)
from app.delivery.metrics import metric_catalogue


def test_safe_ratio_preserves_missing_and_zero_denominator_as_unknown():
    assert safe_ratio(None, 10) is None
    assert safe_ratio(5, None) is None
    assert safe_ratio(5, 0) is None
    assert safe_ratio(7, 8) == 87.5


def test_percentile_is_deterministic_and_handles_sparse_data():
    assert percentile([], 85) is None
    assert percentile([6.2], 85) == 6.2
    assert percentile([1, 2, 3, 4, 5], 85) == 4.4


def test_team_health_enforces_anonymous_minimum():
    hidden = aggregate_team_health([8, 7, 9, 8])
    assert hidden == {
        "value": None,
        "status": "INSUFFICIENT_DATA",
        "responseCount": 4,
        "minimumResponses": ANONYMOUS_TEAM_HEALTH_MINIMUM,
    }
    available = aggregate_team_health([8, 7, 9, 8, 8])
    assert available["value"] == 8
    assert available["status"] == "AVAILABLE"


def test_agile_metric_catalogue_is_versioned_and_explicit_about_missing_data():
    definitions = {item["key"]: item for item in metric_catalogue()}
    for key in (
        "sprint_goal_achievement",
        "commitment_achievement",
        "carryover_rate",
        "forecast_accuracy",
        "cycle_time_p85",
        "backlog_readiness",
        "evidence_coverage",
        "team_health_aggregate",
    ):
        assert definitions[key]["version"] == "1.0"
        assert definitions[key]["missing_data_behaviour"] == "UNKNOWN"
