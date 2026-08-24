from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.database.models.governance import (
    Budget,
    BudgetAlert,
    BudgetOverride,
    BudgetReservation,
    GovernancePolicy,
    GovernedModel,
    ModelPrice,
)

MILLION = Decimal("1000000")
SUPPORTED_SCOPES = ("TENANT", "PROGRAMME", "PROJECT", "AGENT", "MODEL")
PERMITTED_DECISIONS = {
    "ALLOW",
    "ALLOW_WITH_NOTICE",
    "ALLOW_AND_ALERT",
    "ROUTE_TO_LOWER_COST_MODEL",
    "REQUIRE_OVERRIDE_APPROVAL",
    "BLOCK_AI_CALL",
}


class BudgetEnforcementError(RuntimeError):
    def __init__(self, decision: dict):
        super().__init__(decision["reason_codes"][0])
        self.decision = decision


@dataclass(frozen=True)
class BudgetContext:
    tenant_id: str
    trace_id: str
    idempotency_key: str
    model: str
    execution_id: str | None = None
    programme_id: str | None = None
    project_id: str | None = None
    agent_id: str | None = None
    use_case: str = "copilot"
    data_classification: str = "INTERNAL"
    region: str | None = None
    required_capabilities: tuple[str, ...] = ("chat",)
    estimated_input_tokens: int = 0
    reserved_output_tokens: int = 512
    critical: bool = False
    override_id: str | None = None


@dataclass
class ReservationResult:
    decision: dict
    reservations: list[BudgetReservation]
    model: GovernedModel
    price: ModelPrice


class BudgetEnforcementService:
    """Database-backed pre-invocation budget gate and settlement service."""

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def _model(self, db: Session, ctx: BudgetContext) -> GovernedModel:
        now = self._now()
        row = (
            db.query(GovernedModel)
            .filter(
                GovernedModel.provider_model_id == ctx.model,
                GovernedModel.status == "ACTIVE",
                (GovernedModel.tenant_id == ctx.tenant_id)
                | (GovernedModel.tenant_id.is_(None)),
                (GovernedModel.effective_from.is_(None))
                | (GovernedModel.effective_from <= now),
                (GovernedModel.effective_until.is_(None))
                | (GovernedModel.effective_until > now),
            )
            .order_by(
                GovernedModel.tenant_id.desc(),
                GovernedModel.configuration_version.desc(),
            )
            .first()
        )
        if row is None:
            raise BudgetEnforcementError(self._blocked(ctx, "MODEL_NOT_APPROVED"))
        if (
            ctx.use_case not in row.approved_use_cases
            or ctx.use_case in row.prohibited_use_cases
        ):
            raise BudgetEnforcementError(self._blocked(ctx, "USE_CASE_NOT_APPROVED"))
        if ctx.data_classification not in row.allowed_data_classifications:
            raise BudgetEnforcementError(
                self._blocked(ctx, "DATA_CLASSIFICATION_BLOCKED")
            )
        if ctx.region and ctx.region not in row.allowed_regions:
            raise BudgetEnforcementError(self._blocked(ctx, "REGION_BLOCKED"))
        if not set(ctx.required_capabilities).issubset(set(row.capabilities)):
            raise BudgetEnforcementError(self._blocked(ctx, "CAPABILITY_MISMATCH"))
        return row

    def _price(self, db: Session, model: GovernedModel) -> ModelPrice:
        now = self._now()
        price = (
            db.query(ModelPrice)
            .filter(
                ModelPrice.model_id == model.id,
                (ModelPrice.tenant_id == model.tenant_id)
                | (ModelPrice.tenant_id.is_(None)),
                ModelPrice.effective_from <= now,
                (ModelPrice.effective_until.is_(None))
                | (ModelPrice.effective_until > now),
            )
            .order_by(ModelPrice.version.desc())
            .first()
        )
        if price is None:
            raise BudgetEnforcementError(
                self._blocked_model(model.provider_model_id, "MODEL_PRICE_UNKNOWN")
            )
        return price

    @staticmethod
    def estimate(price: ModelPrice, input_tokens: int, output_tokens: int) -> Decimal:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token estimates cannot be negative")
        return (
            Decimal(input_tokens) * price.input_cost_per_million / MILLION
            + Decimal(output_tokens) * price.output_cost_per_million / MILLION
        ).quantize(Decimal("0.00000001"))

    def applicable_budgets(
        self, db: Session, ctx: BudgetContext, model: GovernedModel
    ) -> list[Budget]:
        now = self._now()
        scopes = {
            "TENANT": ctx.tenant_id,
            "PROGRAMME": ctx.programme_id,
            "PROJECT": ctx.project_id,
            "AGENT": ctx.agent_id,
            "MODEL": model.id,
        }
        rows = (
            db.query(Budget)
            .filter(
                Budget.tenant_id == ctx.tenant_id,
                Budget.status == "ACTIVE",
                Budget.effective_from <= now,
                (Budget.effective_until.is_(None)) | (Budget.effective_until > now),
                Budget.scope_type.in_(SUPPORTED_SCOPES),
            )
            .order_by(Budget.scope_type, Budget.scope_id, Budget.id)
            .all()
        )
        return [row for row in rows if scopes.get(row.scope_type) == row.scope_id]

    @staticmethod
    def _period_start(budget: Budget, now: datetime) -> datetime:
        if budget.period == "DAILY":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if budget.period == "WEEKLY":
            start = now - timedelta(days=now.weekday())
            return start.replace(hour=0, minute=0, second=0, microsecond=0)
        if budget.period == "YEARLY":
            return now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _spend(self, db: Session, budget: Budget) -> tuple[Decimal, Decimal]:
        start = self._period_start(budget, self._now())
        settled = (
            db.query(func.coalesce(func.sum(BudgetReservation.settled_amount), 0))
            .filter(
                BudgetReservation.tenant_id == budget.tenant_id,
                BudgetReservation.budget_id == budget.id,
                BudgetReservation.status == "SETTLED",
                BudgetReservation.created_at >= start,
            )
            .scalar()
        )
        reserved = (
            db.query(func.coalesce(func.sum(BudgetReservation.estimated_amount), 0))
            .filter(
                BudgetReservation.tenant_id == budget.tenant_id,
                BudgetReservation.budget_id == budget.id,
                BudgetReservation.status == "RESERVED",
                BudgetReservation.created_at >= start,
            )
            .scalar()
        )
        return Decimal(settled or 0), Decimal(reserved or 0)

    def _override(
        self, db: Session, ctx: BudgetContext, amount: Decimal
    ) -> BudgetOverride | None:
        if not ctx.override_id:
            return None
        row = (
            db.query(BudgetOverride)
            .filter_by(id=ctx.override_id, tenant_id=ctx.tenant_id)
            .with_for_update()
            .first()
        )
        if (
            row is None
            or row.status != "APPROVED"
            or row.expires_at <= self._now()
            or row.uses_remaining <= 0
            or row.remaining_amount < amount
        ):
            return None
        if row.model_restrictions and ctx.model not in row.model_restrictions:
            return None
        return row

    def reserve(self, db: Session, ctx: BudgetContext) -> ReservationResult:
        model = self._model(db, ctx)
        price = self._price(db, model)
        estimate = self.estimate(
            price, ctx.estimated_input_tokens, ctx.reserved_output_tokens
        )
        budgets = self.applicable_budgets(db, ctx, model)
        currencies = {row.currency for row in budgets} | {price.currency}
        if len(currencies) > 1:
            raise BudgetEnforcementError(self._blocked(ctx, "CURRENCY_MISMATCH"))

        existing = (
            db.query(BudgetReservation)
            .filter_by(tenant_id=ctx.tenant_id, idempotency_key=ctx.idempotency_key)
            .all()
        )
        if existing:
            return ReservationResult(
                self._decision(ctx, existing, model, estimate), existing, model, price
            )

        # Updating each budget row in stable order acquires a database write lock.
        # PostgreSQL locks rows; SQLite serializes the write transaction.
        for budget in budgets:
            db.execute(
                update(Budget)
                .where(Budget.id == budget.id, Budget.tenant_id == ctx.tenant_id)
                .values(state_version=Budget.state_version + 1)
            )

        evaluations = []
        blocked = False
        for budget in budgets:
            settled, reserved = self._spend(db, budget)
            projected = settled + reserved + estimate
            ratio = (
                projected / budget.hard_limit * 100
                if budget.hard_limit
                else Decimal("100")
            )
            evaluations.append((budget, settled, reserved, projected, ratio))
            blocked = blocked or projected >= budget.hard_limit

        override = self._override(db, ctx, estimate) if blocked else None
        if blocked and override is None:
            fallback = self._fallback(db, ctx, model, price)
            if fallback is not None:
                routed = self.reserve(
                    db, replace(ctx, model=fallback.provider_model_id)
                )
                routed.decision.update(
                    {
                        "decision": "ROUTE_TO_LOWER_COST_MODEL",
                        "reason_codes": ["APPROVED_LOWER_COST_ROUTE"],
                        "original_model": ctx.model,
                        "fallback_model": fallback.provider_model_id,
                        "selected_model": fallback.provider_model_id,
                    }
                )
                append_audit_event(
                    db,
                    tenant_id=ctx.tenant_id,
                    actor_id="budget-enforcer",
                    action="budget.model.rerouted",
                    target_type="ai_request",
                    target_id=ctx.execution_id or ctx.idempotency_key,
                    trace_id=ctx.trace_id,
                    execution_id=ctx.execution_id,
                    result="ROUTED",
                    model_id=fallback.id,
                    provider=fallback.provider,
                    metadata={
                        "original_model": ctx.model,
                        "fallback_model": fallback.provider_model_id,
                    },
                )
                db.commit()
                return routed
            decision = self._blocked(
                ctx, "HARD_LIMIT_REACHED", budgets, estimate, evaluations
            )
            append_audit_event(
                db,
                tenant_id=ctx.tenant_id,
                actor_id="budget-enforcer",
                action="budget.reservation.blocked",
                target_type="ai_request",
                target_id=ctx.execution_id or ctx.idempotency_key,
                trace_id=ctx.trace_id,
                execution_id=ctx.execution_id,
                result="BLOCKED",
                metadata={
                    "budget_ids": [b.id for b in budgets],
                    "reason_codes": decision["reason_codes"],
                },
            )
            db.commit()
            raise BudgetEnforcementError(decision)

        reservations = []
        now = self._now()
        for budget in budgets:
            reservation = BudgetReservation(
                tenant_id=ctx.tenant_id,
                trace_id=ctx.trace_id,
                execution_id=ctx.execution_id,
                budget_id=budget.id,
                scope_type=budget.scope_type,
                scope_id=budget.scope_id,
                model_id=model.id,
                price_version=price.version,
                estimated_amount=estimate,
                currency=price.currency,
                status="RESERVED",
                idempotency_key=ctx.idempotency_key,
                created_at=now,
                expires_at=now + timedelta(minutes=15),
            )
            db.add(reservation)
            reservations.append(reservation)
        if override:
            override.remaining_amount -= estimate
            override.uses_remaining -= 1
            if override.single_use or override.uses_remaining == 0:
                override.status = "CONSUMED"
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(BudgetReservation)
                .filter_by(tenant_id=ctx.tenant_id, idempotency_key=ctx.idempotency_key)
                .all()
            )
            if not existing:
                raise
            return ReservationResult(
                self._decision(ctx, existing, model, estimate), existing, model, price
            )
        decision = self._decision(ctx, reservations, model, estimate, evaluations)
        self._record_threshold_alerts(db, ctx, evaluations)
        append_audit_event(
            db,
            tenant_id=ctx.tenant_id,
            actor_id="budget-enforcer",
            action="budget.reservation.created",
            target_type="ai_request",
            target_id=ctx.execution_id or ctx.idempotency_key,
            trace_id=ctx.trace_id,
            execution_id=ctx.execution_id,
            result=decision["decision"],
            model_id=model.id,
            provider=model.provider,
            metadata={
                "budget_ids": [b.id for b in budgets],
                "estimated_amount": str(estimate),
                "price_version": price.version,
                "reason_codes": decision["reason_codes"],
            },
        )
        db.commit()
        return ReservationResult(decision, reservations, model, price)

    def _fallback(
        self,
        db: Session,
        ctx: BudgetContext,
        original: GovernedModel,
        original_price: ModelPrice,
    ) -> GovernedModel | None:
        policy = (
            db.query(GovernancePolicy)
            .filter(
                GovernancePolicy.status == "ACTIVE",
                GovernancePolicy.category == "COST_BUDGET",
                (GovernancePolicy.tenant_id == ctx.tenant_id)
                | (GovernancePolicy.tenant_id.is_(None)),
            )
            .order_by(GovernancePolicy.priority, GovernancePolicy.version.desc())
            .first()
        )
        if not policy or not policy.effect.get("allow_lower_cost_routing"):
            return None
        candidates = (
            db.query(GovernedModel)
            .filter(
                GovernedModel.status == "ACTIVE",
                GovernedModel.id != original.id,
                (GovernedModel.tenant_id == ctx.tenant_id)
                | (GovernedModel.tenant_id.is_(None)),
            )
            .all()
        )
        compatible = []
        for candidate in candidates:
            if (
                ctx.use_case not in candidate.approved_use_cases
                or ctx.use_case in candidate.prohibited_use_cases
                or ctx.data_classification not in candidate.allowed_data_classifications
                or (ctx.region and ctx.region not in candidate.allowed_regions)
                or not set(ctx.required_capabilities).issubset(
                    set(candidate.capabilities)
                )
                or (original.context_limit or 0) > (candidate.context_limit or 0)
            ):
                continue
            try:
                price = self._price(db, candidate)
            except BudgetEnforcementError:
                continue
            if price.currency != original_price.currency:
                continue
            cost = self.estimate(
                price, ctx.estimated_input_tokens, ctx.reserved_output_tokens
            )
            original_cost = self.estimate(
                original_price, ctx.estimated_input_tokens, ctx.reserved_output_tokens
            )
            if cost < original_cost:
                compatible.append((cost, candidate))
        return (
            min(compatible, key=lambda item: (item[0], item[1].id))[1]
            if compatible
            else None
        )

    def _record_threshold_alerts(
        self, db: Session, ctx: BudgetContext, evaluations
    ) -> None:
        now = self._now()
        for budget, _settled, _reserved, _projected, ratio in evaluations:
            crossed = max(
                (
                    Decimal(str(value))
                    for value in budget.alert_thresholds
                    if ratio >= Decimal(str(value))
                ),
                default=None,
            )
            if crossed is None:
                continue
            alert_type = "HARD_LIMIT" if crossed >= 100 else f"THRESHOLD_{crossed}"
            period_key = self._period_start(budget, now).isoformat()
            exists = (
                db.query(BudgetAlert.id)
                .filter_by(
                    tenant_id=ctx.tenant_id,
                    budget_id=budget.id,
                    period_key=period_key,
                    alert_type=alert_type,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                BudgetAlert(
                    tenant_id=ctx.tenant_id,
                    budget_id=budget.id,
                    period_key=period_key,
                    alert_type=alert_type,
                    threshold=crossed,
                    trace_id=ctx.trace_id,
                    created_at=now,
                )
            )
            append_audit_event(
                db,
                tenant_id=ctx.tenant_id,
                actor_id="budget-enforcer",
                action="budget.threshold.alert",
                target_type="budget",
                target_id=budget.id,
                trace_id=ctx.trace_id,
                execution_id=ctx.execution_id,
                result=alert_type,
                metadata={"threshold": str(crossed)},
            )

    def settle(
        self, db: Session, ctx: BudgetContext, usage: dict[str, int] | None
    ) -> Decimal | None:
        rows = (
            db.query(BudgetReservation)
            .filter_by(
                tenant_id=ctx.tenant_id,
                idempotency_key=ctx.idempotency_key,
                status="RESERVED",
            )
            .with_for_update()
            .all()
        )
        if not rows:
            return None
        if usage is None:
            for row in rows:
                row.status = "RECONCILIATION_REQUIRED"
                row.failure_reason = "PROVIDER_USAGE_UNKNOWN"
            append_audit_event(
                db,
                tenant_id=ctx.tenant_id,
                actor_id="budget-enforcer",
                action="budget.reconciliation.required",
                target_type="ai_request",
                target_id=ctx.execution_id or ctx.idempotency_key,
                trace_id=ctx.trace_id,
                result="UNKNOWN_USAGE",
                metadata={"reservation_ids": [r.id for r in rows]},
            )
            db.commit()
            return None
        price = (
            db.query(ModelPrice)
            .filter_by(model_id=rows[0].model_id, version=rows[0].price_version)
            .first()
        )
        if price is None:
            raise RuntimeError("Preserved price version is unavailable")
        actual = self.estimate(
            price,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
        now = self._now()
        for row in rows:
            row.status, row.settled_amount, row.settled_at = "SETTLED", actual, now
        append_audit_event(
            db,
            tenant_id=ctx.tenant_id,
            actor_id="budget-enforcer",
            action="budget.reservation.settled",
            target_type="ai_request",
            target_id=ctx.execution_id or ctx.idempotency_key,
            trace_id=ctx.trace_id,
            execution_id=ctx.execution_id,
            result="SETTLED",
            metadata={
                "reservation_ids": [r.id for r in rows],
                "actual_amount": str(actual),
                "estimated_amount": str(rows[0].estimated_amount),
            },
        )
        db.commit()
        return actual

    def release(self, db: Session, ctx: BudgetContext, reason: str) -> None:
        rows = (
            db.query(BudgetReservation)
            .filter_by(
                tenant_id=ctx.tenant_id,
                idempotency_key=ctx.idempotency_key,
                status="RESERVED",
            )
            .with_for_update()
            .all()
        )
        now = self._now()
        for row in rows:
            row.status, row.released_at, row.failure_reason = (
                "RELEASED",
                now,
                reason[:200],
            )
        if rows:
            append_audit_event(
                db,
                tenant_id=ctx.tenant_id,
                actor_id="budget-enforcer",
                action="budget.reservation.released",
                target_type="ai_request",
                target_id=ctx.execution_id or ctx.idempotency_key,
                trace_id=ctx.trace_id,
                execution_id=ctx.execution_id,
                result="RELEASED",
                metadata={
                    "reservation_ids": [r.id for r in rows],
                    "reason": reason[:80],
                },
            )
        db.commit()

    def _decision(self, ctx, rows, model, estimate, evaluations=None):
        max_ratio = max((item[4] for item in (evaluations or [])), default=Decimal("0"))
        decision = "ALLOW"
        reasons = (
            ["NO_APPLICABLE_BUDGET"]
            if not rows and not evaluations
            else ["BELOW_THRESHOLD"]
        )
        if max_ratio >= 90:
            decision, reasons = "ALLOW_AND_ALERT", ["HIGH_WARNING_THRESHOLD"]
        elif max_ratio >= 75:
            decision, reasons = "ALLOW_AND_ALERT", ["WARNING_THRESHOLD"]
        elif max_ratio >= 50:
            decision, reasons = "ALLOW_WITH_NOTICE", ["INFORMATIONAL_THRESHOLD"]
        return {
            "decision": decision,
            "reason_codes": reasons,
            "applicable_budgets": [r.budget_id for r in rows],
            "estimated_request_cost": str(estimate),
            "selected_model": model.provider_model_id,
            "original_model": ctx.model,
            "fallback_model": None,
            "approval_required": False,
            "trace_id": ctx.trace_id,
            "reservation_ids": [r.id for r in rows],
        }

    def _blocked(self, ctx, reason, budgets=None, estimate=None, evaluations=None):
        return {
            "decision": "REQUIRE_OVERRIDE_APPROVAL"
            if ctx.critical
            else "BLOCK_AI_CALL",
            "reason_codes": [reason],
            "applicable_budgets": [b.id for b in budgets or []],
            "current_spend": str(
                max((e[1] for e in evaluations or []), default=Decimal(0))
            ),
            "active_reservations": str(
                max((e[2] for e in evaluations or []), default=Decimal(0))
            ),
            "estimated_request_cost": str(estimate) if estimate is not None else None,
            "projected_spend": str(
                max((e[3] for e in evaluations or []), default=Decimal(0))
            ),
            "threshold": "HARD_LIMIT",
            "selected_model": None,
            "original_model": ctx.model,
            "fallback_model": None,
            "approval_required": ctx.critical,
            "policy_id": None,
            "policy_version": None,
            "trace_id": ctx.trace_id,
        }

    @staticmethod
    def _blocked_model(model: str, reason: str):
        return {
            "decision": "BLOCK_AI_CALL",
            "reason_codes": [reason],
            "applicable_budgets": [],
            "selected_model": None,
            "original_model": model,
            "fallback_model": None,
            "approval_required": False,
            "trace_id": None,
        }


budget_enforcement_service = BudgetEnforcementService()
