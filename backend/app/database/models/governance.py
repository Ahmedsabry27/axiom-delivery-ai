from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _id() -> str:
    return str(uuid4())


class GovernancePolicy(Base):
    __tablename__ = "governance_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "policy_key", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str | None] = mapped_column(String(120), index=True)
    policy_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    effect: Mapped[dict] = mapped_column(JSON, default=dict)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[str | None] = mapped_column(String(36))
    state_version: Mapped[int] = mapped_column(Integer, default=1)


class AccessReview(Base):
    __tablename__ = "governance_access_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewer_id: Mapped[str] = mapped_column(String(255), index=True)
    access_items: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(String(30))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GovernedModel(Base):
    __tablename__ = "governed_models"
    __table_args__ = (
        UniqueConstraint("tenant_id", "model_key", "configuration_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str | None] = mapped_column(String(120), index=True)
    model_key: Mapped[str] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    provider_model_id: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    model_family: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    approved_use_cases: Mapped[list] = mapped_column(JSON, default=list)
    prohibited_use_cases: Mapped[list] = mapped_column(JSON, default=list)
    allowed_data_classifications: Mapped[list] = mapped_column(JSON, default=list)
    allowed_regions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    context_limit: Mapped[int | None] = mapped_column(Integer)
    configuration_version: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelPrice(Base):
    __tablename__ = "model_prices"
    __table_args__ = (UniqueConstraint("model_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    model_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer)
    input_cost_per_million: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    output_cost_per_million: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageRecord(Base):
    __tablename__ = "ai_usage_records"
    __table_args__ = (UniqueConstraint("tenant_id", "execution_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    execution_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), index=True)
    programme_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    model_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True)
    price_version: Mapped[int | None] = mapped_column(Integer)
    input_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    output_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    currency: Mapped[str | None] = mapped_column(String(3))
    cost_estimated: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Budget(Base):
    __tablename__ = "ai_budgets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_type", "scope_id", "period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    scope_type: Mapped[str] = mapped_column(String(30), index=True)
    scope_id: Mapped[str] = mapped_column(String(120), index=True)
    period: Mapped[str] = mapped_column(String(20))
    soft_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    hard_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    alert_thresholds: Mapped[list] = mapped_column(
        JSON, default=lambda: [50, 75, 90, 100]
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(255))
    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "budget_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('RESERVED','SETTLED','RELEASED','EXPIRED','FAILED','RECONCILIATION_REQUIRED')",
            name="ck_budget_reservation_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), index=True)
    budget_id: Mapped[str] = mapped_column(String(36), index=True)
    scope_type: Mapped[str] = mapped_column(String(30), index=True)
    scope_id: Mapped[str] = mapped_column(String(120), index=True)
    model_id: Mapped[str] = mapped_column(String(36), index=True)
    price_version: Mapped[int] = mapped_column(Integer)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    settled_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), default="RESERVED", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(200))


class BudgetAlert(Base):
    __tablename__ = "budget_alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "budget_id", "period_key", "alert_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    budget_id: Mapped[str] = mapped_column(String(36), index=True)
    period_key: Mapped[str] = mapped_column(String(40), index=True)
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BudgetOverride(Base):
    __tablename__ = "budget_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    budget_id: Mapped[str] = mapped_column(String(36), index=True)
    proposed_action_id: Mapped[str | None] = mapped_column(String(36), index=True)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    business_impact: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[str] = mapped_column(String(255), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    single_use: Mapped[bool] = mapped_column(Boolean, default=True)
    uses_remaining: Mapped[int] = mapped_column(Integer, default=1)
    model_restrictions: Mapped[list] = mapped_column(JSON, default=list)
    policy_id: Mapped[str | None] = mapped_column(String(36))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = (UniqueConstraint("tenant_id", "dataset_key", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    dataset_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    use_case: Mapped[str] = mapped_column(String(120))
    cases: Mapped[list] = mapped_column(JSON, default=list)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    dataset_id: Mapped[str] = mapped_column(String(36), index=True)
    dataset_version: Mapped[int] = mapped_column(Integer)
    agent_id: Mapped[str | None] = mapped_column(String(36))
    agent_version: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    model_id: Mapped[str] = mapped_column(String(36), index=True)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    failures: Mapped[list] = mapped_column(JSON, default=list)
    trace_ids: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    test_case_id: Mapped[str] = mapped_column(String(120))
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    passed: Mapped[bool] = mapped_column(Boolean)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    actual_behavior_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_validation: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    failure_category: Mapped[str | None] = mapped_column(String(80))


class AIIncident(Base):
    __tablename__ = "ai_incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    incident_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[str | None] = mapped_column(String(255))
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    affected_tenant_refs: Mapped[list] = mapped_column(JSON, default=list)
    trace_ids: Mapped[list] = mapped_column(JSON, default=list)
    impact_summary: Mapped[str] = mapped_column(Text)
    mitigation: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    corrective_actions: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"
    __table_args__ = (UniqueConstraint("tenant_id", "resource_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    classification: Mapped[str] = mapped_column(String(20))
    retention_days: Mapped[int] = mapped_column(Integer)
    allowed_models: Mapped[list] = mapped_column(JSON, default=list)
    allowed_providers: Mapped[list] = mapped_column(JSON, default=list)
    allowed_regions: Mapped[list] = mapped_column(JSON, default=list)
    logging_controls: Mapped[dict] = mapped_column(JSON, default=dict)
    export_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
