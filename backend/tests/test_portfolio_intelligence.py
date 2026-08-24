from datetime import date
from decimal import Decimal

from app.database.models.delivery import (
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    PortfolioInvestmentSnapshot,
    PortfolioOutcomeLink,
    PortfolioStrategicOutcome,
)
from app.delivery.portfolio_service import PortfolioIntelligenceService


def test_workspace_is_tenant_scoped_and_preserves_missing_financials(db_session):
    portfolio = DeliveryPortfolio(
        tenant_id="tenant-a", name="Enterprise", status="ACTIVE"
    )
    db_session.add(portfolio)
    db_session.flush()
    programme = DeliveryProgramme(
        tenant_id="tenant-a", portfolio_id=portfolio.id, name="Digital", status="ACTIVE"
    )
    db_session.add(programme)
    db_session.flush()
    db_session.add(
        DeliveryProject(
            tenant_id="tenant-a",
            programme_id=programme.id,
            name="Onboarding",
            status="AT_RISK",
        )
    )
    other = DeliveryPortfolio(tenant_id="tenant-b", name="Private", status="ACTIVE")
    db_session.add(other)
    db_session.commit()

    result = PortfolioIntelligenceService(db_session, "tenant-a", "user-a").workspace()

    assert [item["name"] for item in result["portfolios"]] == ["Enterprise"]
    assert result["projects"][0]["health"]["status"] == "RED"
    assert result["projects"][0]["approvedBudget"] is None
    assert result["health"]["version"] == "portfolio-health-v1"


def test_decimal_financial_values_are_serialized_without_float_conversion(db_session):
    portfolio = DeliveryPortfolio(tenant_id="tenant-a", name="Enterprise")
    db_session.add(portfolio)
    db_session.flush()
    programme = DeliveryProgramme(
        tenant_id="tenant-a", portfolio_id=portfolio.id, name="Digital"
    )
    db_session.add(programme)
    db_session.flush()
    db_session.add(
        DeliveryProject(
            tenant_id="tenant-a",
            programme_id=programme.id,
            name="Payments",
            record_metadata={"approved_budget": "1000000.125", "currency": "GBP"},
        )
    )
    db_session.commit()

    project = PortfolioIntelligenceService(
        db_session, "tenant-a", "user-a"
    ).workspace()["projects"][0]
    assert project["approvedBudget"] == "1000000.12"
    assert project["currency"] == "GBP"


def test_persisted_outcomes_and_decimal_snapshots_are_exposed_and_redactable(db_session):
    portfolio = DeliveryPortfolio(tenant_id="tenant-a", name="Enterprise")
    db_session.add(portfolio)
    db_session.flush()
    programme = DeliveryProgramme(tenant_id="tenant-a", portfolio_id=portfolio.id, name="Digital")
    db_session.add(programme)
    db_session.flush()
    project = DeliveryProject(tenant_id="tenant-a", programme_id=programme.id, name="Payments")
    outcome = PortfolioStrategicOutcome(
        tenant_id="tenant-a", portfolio_id=portfolio.id, name="Faster payments", target_value="2", unit="seconds"
    )
    db_session.add_all([project, outcome])
    db_session.flush()
    db_session.add_all([
        PortfolioOutcomeLink(tenant_id="tenant-a", outcome_id=outcome.id, entity_type="PROJECT", entity_id=project.id, contribution=100),
        PortfolioInvestmentSnapshot(
            tenant_id="tenant-a", entity_type="PROJECT", entity_id=project.id,
            reporting_period=date(2026, 8, 1), currency="GBP",
            approved_budget=Decimal("123456.7890"), source_system="ERP",
        ),
    ])
    db_session.commit()

    visible = PortfolioIntelligenceService(db_session, "tenant-a", "user-a").workspace()
    assert visible["outcomes"][0]["links"][0]["entityId"] == project.id
    assert visible["projects"][0]["approvedBudget"] == "123456.7890"
    assert visible["projects"][0]["financialSource"] == "ERP"

    restricted = PortfolioIntelligenceService(db_session, "tenant-a", "user-a").workspace(financial_access=False)
    assert restricted["investment"]["authorized"] is False
    assert restricted["projects"][0]["approvedBudget"] is None
