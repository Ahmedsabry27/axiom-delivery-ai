from datetime import date

import pytest
from sqlalchemy import func, select

from app.database.models.delivery import DeliveryPortfolio, DeliveryProject
from app.seed.demo_data import (
    DEMO_TENANT,
    DemoSeedError,
    assert_safe_database,
    assert_safe_environment,
    reset_demo,
    seed_demo,
    stable_id,
    validate_demo,
)


def allow_seed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_DEMO_SEED", "true")


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_seed_refuses_unsafe_environments(monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("ALLOW_DEMO_SEED", "true")
    with pytest.raises(DemoSeedError):
        assert_safe_environment(DEMO_TENANT)


def test_seed_refuses_missing_flag_and_non_demo_tenant(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)
    with pytest.raises(DemoSeedError):
        assert_safe_environment(DEMO_TENANT)
    monkeypatch.setenv("ALLOW_DEMO_SEED", "true")
    with pytest.raises(DemoSeedError):
        assert_safe_environment("customer-tenant")


def test_in_memory_database_is_accepted(db_session):
    assert_safe_database(db_session)


def test_seed_is_idempotent_stable_and_financially_reconciled(db_session, monkeypatch):
    allow_seed(monkeypatch)
    reference_date = date(2026, 10, 6)
    first = seed_demo(db_session, reference_date)
    db_session.commit()
    first_validation = validate_demo(db_session)
    second = seed_demo(db_session, reference_date)
    db_session.commit()
    second_validation = validate_demo(db_session)

    assert first == second
    assert first_validation == second_validation
    assert first_validation["delivery_projects"] == 8
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DeliveryPortfolio)
            .where(DeliveryPortfolio.tenant_id == DEMO_TENANT)
        )
        == 1
    )
    assert stable_id("delivery_projects", "identity") == db_session.scalar(
        select(DeliveryProject.id).where(
            DeliveryProject.name == "Identity Modernisation"
        )
    )


def test_reset_is_exact_and_preserves_other_tenants(db_session, monkeypatch):
    allow_seed(monkeypatch)
    seed_demo(db_session, date(2026, 10, 6))
    other = DeliveryPortfolio(tenant_id="other", name="Customer portfolio")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(DemoSeedError):
        reset_demo(db_session, DEMO_TENANT, "wrong")
    reset_demo(db_session, DEMO_TENANT, DEMO_TENANT)

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DeliveryPortfolio)
            .where(DeliveryPortfolio.tenant_id == DEMO_TENANT)
        )
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DeliveryPortfolio)
            .where(DeliveryPortfolio.tenant_id == "other")
        )
        == 1
    )
