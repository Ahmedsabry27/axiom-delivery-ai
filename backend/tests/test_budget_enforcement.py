from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.governed_provider import GovernedProvider, authorized_provider_invocation
from app.ai.models import AIMessage, AIMessageRole, AIResponse
from app.database.base import Base
from app.database.models.governance import (
    Budget,
    BudgetOverride,
    BudgetReservation,
    GovernancePolicy,
    GovernedModel,
    ModelPrice,
)
from app.governance.budget_enforcement import (
    BudgetContext,
    BudgetEnforcementError,
    budget_enforcement_service,
)


def seed_model(
    db,
    *,
    model_name="approved-model",
    status="ACTIVE",
    currency="USD",
    unit_price="1000",
):
    now = datetime.now(UTC).replace(tzinfo=None)
    model = GovernedModel(
        tenant_id="tenant-a",
        model_key=model_name,
        provider="openai",
        provider_model_id=model_name,
        display_name=model_name,
        model_family="test",
        capabilities=["chat", "structured_output"],
        approved_use_cases=["copilot"],
        prohibited_use_cases=[],
        allowed_data_classifications=["INTERNAL"],
        allowed_regions=["eu"],
        status=status,
        context_limit=8192,
        configuration_version=1,
        effective_from=now - timedelta(days=1),
        created_by="author",
        created_at=now - timedelta(days=1),
    )
    db.add(model)
    db.flush()
    price = ModelPrice(
        model_id=model.id,
        tenant_id="tenant-a",
        version=3,
        input_cost_per_million=Decimal(unit_price),
        output_cost_per_million=Decimal(unit_price),
        currency=currency,
        effective_from=now - timedelta(days=1),
    )
    db.add(price)
    db.commit()
    return model, price


def seed_budget(
    db, *, hard="1.00", scope_type="TENANT", scope_id="tenant-a", currency="USD"
):
    now = datetime.now(UTC).replace(tzinfo=None)
    row = Budget(
        tenant_id="tenant-a",
        scope_type=scope_type,
        scope_id=scope_id,
        period="MONTHLY",
        soft_limit=Decimal(hard) * Decimal("0.75"),
        hard_limit=Decimal(hard),
        currency=currency,
        alert_thresholds=[50, 75, 90, 100],
        effective_from=now - timedelta(days=1),
        status="ACTIVE",
        created_by="admin",
    )
    db.add(row)
    db.commit()
    return row


def context(key="request-1", **changes):
    values = dict(
        tenant_id="tenant-a",
        trace_id=f"trace-{key}",
        idempotency_key=key,
        model="approved-model",
        region="eu",
        estimated_input_tokens=100,
        reserved_output_tokens=100,
    )
    values.update(changes)
    return BudgetContext(**values)


def test_no_applicable_budget_is_documented_allow(db_session):
    seed_model(db_session)
    result = budget_enforcement_service.reserve(db_session, context())
    assert result.decision["decision"] == "ALLOW"
    assert result.decision["reason_codes"] == ["NO_APPLICABLE_BUDGET"]
    assert result.reservations == []


@pytest.mark.parametrize(
    ("hard", "decision", "reason"),
    [
        ("1.00", "ALLOW", "BELOW_THRESHOLD"),
        ("0.40", "ALLOW_WITH_NOTICE", "INFORMATIONAL_THRESHOLD"),
        ("0.25", "ALLOW_AND_ALERT", "WARNING_THRESHOLD"),
        ("0.21", "ALLOW_AND_ALERT", "HIGH_WARNING_THRESHOLD"),
    ],
)
def test_threshold_decisions_are_deterministic(db_session, hard, decision, reason):
    seed_model(db_session)
    seed_budget(db_session, hard=hard)
    result = budget_enforcement_service.reserve(db_session, context(hard))
    assert result.decision["decision"] == decision
    assert result.decision["reason_codes"] == [reason]


def test_hard_limit_blocks_without_creating_reservation(db_session):
    seed_model(db_session)
    budget = seed_budget(db_session, hard="0.10")
    with pytest.raises(BudgetEnforcementError) as caught:
        budget_enforcement_service.reserve(db_session, context())
    assert caught.value.decision["decision"] == "BLOCK_AI_CALL"
    assert (
        db_session.query(BudgetReservation).filter_by(budget_id=budget.id).count() == 0
    )


def test_multiple_budgets_use_most_restrictive_result(db_session):
    model, _ = seed_model(db_session)
    seed_budget(db_session, hard="1.00")
    seed_budget(db_session, hard="0.10", scope_type="MODEL", scope_id=model.id)
    with pytest.raises(BudgetEnforcementError):
        budget_enforcement_service.reserve(db_session, context())
    assert db_session.query(BudgetReservation).count() == 0


def test_currency_mismatch_fails_closed(db_session):
    seed_model(db_session)
    seed_budget(db_session, currency="EUR")
    with pytest.raises(BudgetEnforcementError) as caught:
        budget_enforcement_service.reserve(db_session, context())
    assert caught.value.decision["reason_codes"] == ["CURRENCY_MISMATCH"]


def test_unknown_unapproved_and_incompatible_models_fail_closed(db_session):
    with pytest.raises(BudgetEnforcementError):
        budget_enforcement_service.reserve(db_session, context())
    seed_model(db_session, status="DISABLED")
    with pytest.raises(BudgetEnforcementError):
        budget_enforcement_service.reserve(db_session, context("disabled"))


def test_reservation_is_idempotent_and_preserves_price_version(db_session):
    seed_model(db_session)
    seed_budget(db_session)
    first = budget_enforcement_service.reserve(db_session, context())
    second = budget_enforcement_service.reserve(db_session, context())
    assert first.reservations[0].id == second.reservations[0].id
    assert second.reservations[0].price_version == 3
    assert db_session.query(BudgetReservation).count() == 1


def test_settlement_uses_actual_usage_and_decimal_precision(db_session):
    seed_model(db_session)
    seed_budget(db_session)
    result = budget_enforcement_service.reserve(db_session, context())
    actual = budget_enforcement_service.settle(
        db_session, context(), {"prompt_tokens": 25, "completion_tokens": 75}
    )
    db_session.refresh(result.reservations[0])
    assert actual == Decimal("0.10000000")
    assert result.reservations[0].status == "SETTLED"
    assert result.reservations[0].settled_amount == Decimal("0.10000000")


def test_release_and_unknown_usage_reconciliation(db_session):
    seed_model(db_session)
    seed_budget(db_session)
    released = budget_enforcement_service.reserve(db_session, context("release"))
    budget_enforcement_service.release(
        db_session, context("release"), "provider failed"
    )
    db_session.refresh(released.reservations[0])
    assert released.reservations[0].status == "RELEASED"
    unknown = budget_enforcement_service.reserve(db_session, context("unknown"))
    assert (
        budget_enforcement_service.settle(db_session, context("unknown"), None) is None
    )
    db_session.refresh(unknown.reservations[0])
    assert unknown.reservations[0].status == "RECONCILIATION_REQUIRED"


def test_approved_override_is_bounded_and_single_use(db_session):
    seed_model(db_session)
    budget = seed_budget(db_session, hard="0.10")
    now = datetime.now(UTC).replace(tzinfo=None)
    override = BudgetOverride(
        tenant_id="tenant-a",
        budget_id=budget.id,
        requested_amount=Decimal("0.30"),
        remaining_amount=Decimal("0.30"),
        scope={},
        reason="critical delivery request",
        business_impact="release",
        requested_by="requester",
        approved_by="approver",
        status="APPROVED",
        expires_at=now + timedelta(hours=1),
        single_use=True,
        uses_remaining=1,
        model_restrictions=["approved-model"],
        evidence=[],
        created_at=now,
        decided_at=now,
    )
    db_session.add(override)
    db_session.commit()
    allowed = budget_enforcement_service.reserve(
        db_session, context("override", override_id=override.id, critical=True)
    )
    assert allowed.reservations
    db_session.refresh(override)
    assert override.status == "CONSUMED"
    with pytest.raises(BudgetEnforcementError):
        budget_enforcement_service.reserve(
            db_session,
            context("override-again", override_id=override.id, critical=True),
        )


def test_cross_tenant_budget_is_never_resolved(db_session):
    seed_model(db_session)
    budget = seed_budget(db_session)
    budget.tenant_id = "tenant-b"
    db_session.commit()
    result = budget_enforcement_service.reserve(db_session, context())
    assert result.reservations == []


def test_only_compatible_active_lower_cost_model_can_be_routed(db_session):
    seed_model(db_session)
    fallback, _ = seed_model(db_session, model_name="approved-cheap", unit_price="100")
    seed_budget(db_session, hard="0.10")
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add(
        GovernancePolicy(
            tenant_id="tenant-a",
            policy_key="lower-cost-route",
            name="Approved lower-cost routing",
            category="COST_BUDGET",
            version=1,
            status="ACTIVE",
            priority=1,
            conditions={},
            effect={"allow_lower_cost_routing": True},
            reason_codes=["BUDGET_ROUTE"],
            created_by="author",
            approved_by="approver",
            created_at=now,
            activated_at=now,
            description="",
        )
    )
    db_session.commit()
    result = budget_enforcement_service.reserve(db_session, context("fallback"))
    assert result.model.id == fallback.id
    assert result.decision["decision"] == "ROUTE_TO_LOWER_COST_MODEL"
    assert result.decision["original_model"] == "approved-model"
    assert result.decision["fallback_model"] == "approved-cheap"


def test_concurrent_requests_near_limit_allow_only_one(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-budget.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as setup:
        seed_model(setup)
        seed_budget(setup, hard="0.30")
    barrier = Barrier(2)

    def reserve(key):
        with sessions() as db:
            barrier.wait()
            try:
                budget_enforcement_service.reserve(db, context(key))
                return "allowed"
            except BudgetEnforcementError:
                return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, ("concurrent-a", "concurrent-b")))
    assert sorted(outcomes) == ["allowed", "blocked"]
    with sessions() as db:
        assert db.query(BudgetReservation).filter_by(status="RESERVED").count() == 1


def test_provider_guard_rejects_direct_invocation_without_reservation():
    class Stub:
        def ask(self, messages):
            return AIResponse(text="ok")

        def stream(self, messages):
            return iter(())

    provider = GovernedProvider(Stub())
    messages = [AIMessage(role=AIMessageRole.USER, content="safe test")]
    with pytest.raises(RuntimeError, match="no committed budget authorization"):
        provider.ask(messages)
    with authorized_provider_invocation():
        assert provider.ask(messages).text == "ok"
