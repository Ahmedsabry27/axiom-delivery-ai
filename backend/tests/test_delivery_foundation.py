from app.delivery.copilot import (
    DeliveryIntent,
    classify_delivery_intent,
    mentioned_entity,
    validate_confidence,
)
from app.delivery.domain import DeliveryHealth, Portfolio, RAIDType, contract_metadata
from app.delivery.intelligence import attention_score, portfolio_health
from app.delivery.intelligence import sprint_predictability as scored_predictability
from app.delivery.metrics import (
    METRIC_DEFINITIONS,
    carryover_rate,
    commitment_achievement,
    risk_exposure,
    sprint_predictability,
)


def test_domain_contract_is_tenant_scoped():
    portfolio = Portfolio(
        id="portfolio-1", tenant_id="tenant-a", name="Synthetic Portfolio"
    )
    assert portfolio.tenant_id == "tenant-a"
    assert portfolio.health is DeliveryHealth.UNKNOWN
    assert "DEPENDENCY" in contract_metadata()["raid_types"]
    assert RAIDType.DEPENDENCY.value == "DEPENDENCY"


def test_required_metric_catalogue_is_complete_and_versioned():
    keys = {metric.key for metric in METRIC_DEFINITIONS}
    assert {
        "portfolio_health",
        "sprint_predictability",
        "release_readiness",
        "risk_exposure",
    } <= keys
    assert all(
        metric.version and metric.missing_data_behaviour == "UNKNOWN"
        for metric in METRIC_DEFINITIONS
    )


def test_percentage_calculations_and_missing_data():
    assert sprint_predictability(87, 100) == 87
    assert commitment_achievement(9, 10) == 90
    assert carryover_rate(2, 10) == 20
    assert sprint_predictability(0, 0) is None
    assert commitment_achievement(None, 10) is None


def test_risk_exposure():
    assert risk_exposure(4, 5) == 20
    assert risk_exposure(None, 5) is None


def test_portfolio_health_is_weighted_and_handles_partial_data():
    complete = portfolio_health(
        {"project": 90, "release": 80, "risk": 70, "dependency": 60, "milestone": 100}
    )
    assert (
        complete.value == 80.5 and complete.status == "GREEN" and not complete.partial
    )
    partial = portfolio_health({"project": 90, "release": 80, "risk": 70})
    assert partial.value is not None and partial.partial
    assert portfolio_health({"project": 90}).status == "UNKNOWN"


def test_scored_predictability_falls_back_to_counts_and_attention_is_explainable():
    result = scored_predictability(None, None, 10, 8)
    assert result.value == 80 and result.partial and result.status == "AMBER"
    attention = attention_score(impact=5, urgency=5, critical_path=True, age_periods=2)
    assert attention.value == 95 and attention.factors["critical_path"] == 25


def test_delivery_copilot_routes_without_bypassing_approval():
    assert (
        classify_delivery_intent("What is threatening Release 4?").intent
        is DeliveryIntent.RELEASE_RISK
    )
    action = classify_delivery_intent("Draft an escalation for them")
    assert (
        action.intent is DeliveryIntent.PROPOSED_ACTION_GENERATE
        and action.approval_required
    )
    assert mentioned_entity("Summarize Sprint 24") == {
        "type": "Sprint",
        "name": "Sprint 24",
    }
    assert validate_confidence(94, 6) == 94 and validate_confidence(80, 0) == 0
