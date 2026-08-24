from app.delivery.sprint_intelligence import (
    detect_anti_patterns,
    forecast,
    sprint_health,
    sprint_metrics,
    work_item_risk,
)


def test_metrics_distinguish_original_scope_and_missing_data():
    result = sprint_metrics(
        original_points=82,
        completed_original=54,
        completed_total=54,
        scope_added=8,
        scope_removed=0,
        blocked_points=11,
        active_points=36,
        blocker_ages=[4, 2],
        defects=3,
        completed_items=9,
    )
    assert result["predictability"]["value"] == 65.85
    assert result["scope_change_rate"]["value"] == 9.76
    assert (
        sprint_metrics(
            original_points=None,
            completed_original=None,
            completed_total=None,
            scope_added=None,
            scope_removed=None,
            blocked_points=None,
            active_points=None,
            blocker_ages=[],
            defects=None,
            completed_items=None,
        )["predictability"]["status"]
        == "UNKNOWN"
    )


def test_health_forecast_risk_and_rules_are_explainable():
    health = sprint_health(
        {
            "delivery_progress": 72,
            "goal_confidence": 68,
            "blocked_work": 62,
            "scope_stability": 86,
            "dependency_health": 65,
            "backlog_readiness": 71,
            "quality": 80,
        }
    )
    assert health["status"] == "AMBER" and health["score"] is not None
    assert sprint_health({"delivery_progress": 80})["status"] == "UNKNOWN"
    result = forecast(
        completed=54,
        elapsed_days=7,
        total_days=10,
        historical_completed=[70, 76, 74],
        original_points=82,
        blocked_points=11,
        scope_added=8,
    )
    assert result["completed_points"] == 70.8 and result["goal_confidence"] < 90
    assert (
        work_item_risk(
            blocked_days=4,
            goal_critical=True,
            remaining_points=8,
            days_remaining=3,
            dependency=True,
        )["level"]
        == "CRITICAL"
    )
    rules = detect_anti_patterns(
        {
            "scope_injection_rate": 14,
            "oldest_blocker_days": 4,
            "wip_items": 9,
            "qa_queue_items": 4,
            "readiness": 70,
            "carryover_rate": 22,
        }
    )
    assert len(rules) == 6
