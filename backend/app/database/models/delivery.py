from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def uid():
    return str(uuid.uuid4())


def dependency_reference():
    return f"D-{uuid.uuid4().hex[:8].upper()}"


def now():
    return datetime.now(UTC)


class DeliveryRecord:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PLANNED")
    source_system: Mapped[str] = mapped_column(
        String(40), nullable=False, default="MANUAL"
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    owner_id: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    record_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DeliveryPortfolio(DeliveryRecord, Base):
    __tablename__ = "delivery_portfolios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "external_id"),
        Index("ix_delivery_portfolio_tenant_status", "tenant_id", "status"),
    )


class PortfolioStrategicOutcome(DeliveryRecord, Base):
    __tablename__ = "portfolio_strategic_outcomes"
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_value: Mapped[str | None] = mapped_column(String(120))
    current_value: Mapped[str | None] = mapped_column(String(120))
    unit: Mapped[str | None] = mapped_column(String(60))
    target_date: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "portfolio_id"],
            ["delivery_portfolios.tenant_id", "delivery_portfolios.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_portfolio_outcome_tenant_portfolio", "tenant_id", "portfolio_id"),
    )


class PortfolioOutcomeLink(Base):
    __tablename__ = "portfolio_outcome_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    outcome_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    contribution: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "outcome_id"],
            [
                "portfolio_strategic_outcomes.tenant_id",
                "portfolio_strategic_outcomes.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "outcome_id", "entity_type", "entity_id"),
        CheckConstraint(
            "entity_type IN ('PROGRAMME', 'PROJECT')",
            name="ck_portfolio_outcome_link_entity",
        ),
        Index(
            "ix_portfolio_outcome_link_entity", "tenant_id", "entity_type", "entity_id"
        ),
    )


class PortfolioInvestmentSnapshot(Base):
    __tablename__ = "portfolio_investment_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    approved_budget: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    actual_spend: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    forecast: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    committed: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    contingency: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    source_system: Mapped[str] = mapped_column(
        String(80), nullable=False, default="MANUAL"
    )
    source_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "entity_id", "reporting_period"),
        CheckConstraint(
            "entity_type IN ('PORTFOLIO', 'PROGRAMME', 'PROJECT')",
            name="ck_portfolio_investment_entity",
        ),
        Index("ix_portfolio_investment_scope", "tenant_id", "entity_type", "entity_id"),
    )


class DeliveryProgramme(DeliveryRecord, Base):
    __tablename__ = "delivery_programmes"
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "portfolio_id"],
            ["delivery_portfolios.tenant_id", "delivery_portfolios.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_programme_tenant_portfolio", "tenant_id", "portfolio_id"),
    )


class DeliveryProject(DeliveryRecord, Base):
    __tablename__ = "delivery_projects"
    programme_id: Mapped[str] = mapped_column(String(36), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "programme_id"],
            ["delivery_programmes.tenant_id", "delivery_programmes.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_project_tenant_programme", "tenant_id", "programme_id"),
    )


class DeliveryTeam(DeliveryRecord, Base):
    __tablename__ = "delivery_teams"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capacity: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_team_tenant_project", "tenant_id", "project_id"),
    )


class DeliverySprint(DeliveryRecord, Base):
    __tablename__ = "delivery_sprints"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    team_id: Mapped[str] = mapped_column(String(36), nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    original_committed_points: Mapped[float | None] = mapped_column(Float)
    completed_original_points: Mapped[float | None] = mapped_column(Float)
    completed_points: Mapped[float | None] = mapped_column(Float)
    scope_added_points: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    scope_removed_points: Mapped[float] = mapped_column(
        Float, default=0, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["delivery_teams.tenant_id", "delivery_teams.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_delivery_sprint_tenant_team_status", "tenant_id", "team_id", "status"
        ),
        Index("ix_delivery_sprint_tenant_dates", "tenant_id", "start_date", "end_date"),
    )


class DeliveryRelease(DeliveryRecord, Base):
    __tablename__ = "delivery_releases"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date)
    readiness_score: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_release_tenant_project", "tenant_id", "project_id"),
    )


class DeliveryWorkItem(DeliveryRecord, Base):
    __tablename__ = "delivery_work_items"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    item_kind: Mapped[str] = mapped_column(
        String(40), default="WORK_ITEM", nullable=False
    )
    story_points: Mapped[float | None] = mapped_column(Float)
    assignee_id: Mapped[str | None] = mapped_column(String(255))
    goal_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_after_start: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    removed_after_start: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
            ondelete="SET NULL",
        ),
        Index(
            "ix_delivery_work_tenant_sprint_status", "tenant_id", "sprint_id", "status"
        ),
        Index("ix_delivery_work_tenant_owner", "tenant_id", "assignee_id"),
    )


class DeliveryDefect(DeliveryRecord, Base):
    __tablename__ = "delivery_defects"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    work_item_id: Mapped[str | None] = mapped_column(String(36))
    severity: Mapped[str | None] = mapped_column(String(30))
    escaped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_item_id"],
            ["delivery_work_items.tenant_id", "delivery_work_items.id"],
        ),
        Index("ix_delivery_defect_tenant_sprint", "tenant_id", "sprint_id"),
    )


class DeliveryRAIDItem(DeliveryRecord, Base):
    __tablename__ = "delivery_raid_items"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    release_id: Mapped[str | None] = mapped_column(String(36))
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(30))
    impact: Mapped[str | None] = mapped_column(String(30))
    probability: Mapped[str | None] = mapped_column(String(30))
    residual_impact: Mapped[str | None] = mapped_column(String(30))
    residual_probability: Mapped[str | None] = mapped_column(String(30))
    exposure_score: Mapped[int | None] = mapped_column(Integer)
    exposure_band: Mapped[str | None] = mapped_column(String(30))
    residual_exposure_score: Mapped[int | None] = mapped_column(Integer)
    residual_exposure_band: Mapped[str | None] = mapped_column(String(30))
    attention_score: Mapped[int | None] = mapped_column(Integer)
    attention_reasons: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    identified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_reason: Mapped[str | None] = mapped_column(Text)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    programme_id: Mapped[str | None] = mapped_column(String(36))
    team_id: Mapped[str | None] = mapped_column(String(36))
    work_item_id: Mapped[str | None] = mapped_column(String(36))
    defect_id: Mapped[str | None] = mapped_column(String(36))
    dependency_id: Mapped[str | None] = mapped_column(String(36))
    trigger: Mapped[str | None] = mapped_column(Text)
    mitigation_plan: Mapped[str | None] = mapped_column(Text)
    contingency_plan: Mapped[str | None] = mapped_column(Text)
    risk_response: Mapped[str | None] = mapped_column(String(30))
    validation_owner_id: Mapped[str | None] = mapped_column(String(255))
    validation_due_date: Mapped[date | None] = mapped_column(Date)
    validation_method: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str | None] = mapped_column(String(30))
    severity: Mapped[str | None] = mapped_column(String(30))
    containment_plan: Mapped[str | None] = mapped_column(Text)
    resolution_plan: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    critical_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_owner_id: Mapped[str | None] = mapped_column(String(255))
    rationale: Mapped[str | None] = mapped_column(Text)
    completion_evidence_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["delivery_releases.tenant_id", "delivery_releases.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "milestone_id"],
            ["delivery_milestones.tenant_id", "delivery_milestones.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "programme_id"],
            ["delivery_programmes.tenant_id", "delivery_programmes.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["delivery_teams.tenant_id", "delivery_teams.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_item_id"],
            ["delivery_work_items.tenant_id", "delivery_work_items.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "defect_id"],
            ["delivery_defects.tenant_id", "delivery_defects.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "reference"),
        Index(
            "ix_delivery_raid_tenant_type_status", "tenant_id", "item_type", "status"
        ),
        Index("ix_delivery_raid_tenant_due", "tenant_id", "due_date"),
        Index("ix_delivery_raid_tenant_attention", "tenant_id", "attention_score"),
        Index("ix_delivery_raid_tenant_owner", "tenant_id", "owner_id"),
        Index("ix_delivery_raid_tenant_release", "tenant_id", "release_id"),
    )


class DeliveryMilestone(DeliveryRecord, Base):
    __tablename__ = "delivery_milestones"
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    release_id: Mapped[str | None] = mapped_column(String(36))
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    description: Mapped[str | None] = mapped_column(Text)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "release_id"],
            ["delivery_releases.tenant_id", "delivery_releases.id"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "actual_date IS NULL OR status IN ('COMPLETED', 'CANCELLED')",
            name="ck_milestone_actual_status",
        ),
        CheckConstraint(
            "forecast_date IS NULL OR forecast_date >= planned_date",
            name="ck_milestone_forecast_date",
        ),
        Index(
            "ix_milestone_tenant_project_status", "tenant_id", "project_id", "status"
        ),
        Index(
            "ix_milestone_tenant_critical_date", "tenant_id", "critical", "planned_date"
        ),
    )


class DeliveryDependency(DeliveryRecord, Base):
    __tablename__ = "delivery_dependencies"
    reference: Mapped[str] = mapped_column(
        String(40), default=dependency_reference, nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    dependency_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        String(40), default="DEPENDS_ON", nullable=False
    )
    impact: Mapped[str | None] = mapped_column(String(30))
    priority: Mapped[str | None] = mapped_column(String(30))
    provider_owner_id: Mapped[str | None] = mapped_column(String(255))
    consumer_owner_id: Mapped[str | None] = mapped_column(String(255))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    required_by_date: Mapped[date | None] = mapped_column(Date)
    committed_resolution_date: Mapped[date | None] = mapped_column(Date)
    forecast_resolution_date: Mapped[date | None] = mapped_column(Date)
    actual_resolution_date: Mapped[date | None] = mapped_column(Date)
    identified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    blocked_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_date: Mapped[date | None] = mapped_column(Date)
    critical_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "reference"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["delivery_projects.tenant_id", "delivery_projects.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR status IN ('RESOLVED', 'CLOSED')",
            name="ck_dependency_resolved_status",
        ),
        Index(
            "ix_dependency_tenant_project_status", "tenant_id", "project_id", "status"
        ),
        Index(
            "ix_dependency_tenant_critical_due",
            "tenant_id",
            "critical_path",
            "required_by_date",
        ),
        Index("ix_dependency_tenant_owner", "tenant_id", "owner_id"),
        Index(
            "ix_dependency_tenant_status_required",
            "tenant_id",
            "status",
            "required_by_date",
        ),
        Index(
            "ix_dependency_tenant_forecast",
            "tenant_id",
            "forecast_resolution_date",
        ),
    )


class DeliveryDependencyEndpoint(Base):
    __tablename__ = "delivery_dependency_endpoints"
    dependency_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    direction: Mapped[str] = mapped_column(String(10), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "direction IN ('SOURCE', 'TARGET')", name="ck_dependency_endpoint_direction"
        ),
        CheckConstraint(
            "entity_type IN ('PORTFOLIO','PROGRAMME','PROJECT','TEAM','SPRINT','RELEASE','MILESTONE','EPIC','WORK_ITEM','DEFECT','SYSTEM','SERVICE','ENVIRONMENT','VENDOR','EXTERNAL_PARTY')",
            name="ck_dependency_endpoint_type",
        ),
        UniqueConstraint("tenant_id", "dependency_id", "direction"),
        Index("ix_dependency_endpoint_entity", "tenant_id", "entity_type", "entity_id"),
        Index(
            "ix_dependency_endpoint_direction_entity",
            "tenant_id",
            "direction",
            "entity_type",
            "entity_id",
        ),
    )


class DeliveryDependencyHistory(Base):
    __tablename__ = "delivery_dependency_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    dependency_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    change_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="CASCADE",
        ),
        Index(
            "ix_dependency_history_tenant_item",
            "tenant_id",
            "dependency_id",
            "changed_at",
        ),
    )


class DeliveryDependencyScenario(Base):
    __tablename__ = "delivery_dependency_scenarios"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    dependency_id: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)
    change_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    baseline_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scenario_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    difference: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="SAVED", nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="CASCADE",
        ),
        Index(
            "ix_dependency_scenario_tenant_item",
            "tenant_id",
            "dependency_id",
            "created_at",
        ),
    )


class DetectedDependencyCandidate(Base):
    __tablename__ = "delivery_dependency_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    provider_entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    consumer_entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    consumer_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    affected_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    possible_duplicates: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    possible_cycle: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    suggested_owner: Mapped[str | None] = mapped_column(String(255))
    suggested_required_by_date: Mapped[date | None] = mapped_column(Date)
    suggested_priority: Mapped[str | None] = mapped_column(String(20))
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    detected_by_agent: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissal_reason: Mapped[str | None] = mapped_column(Text)
    accepted_dependency_id: Mapped[str | None] = mapped_column(String(36))
    merged_dependency_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "trace_id"),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "merged_dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_dependency_candidate_tenant_status",
            "tenant_id",
            "status",
            "detected_at",
        ),
    )


class DetectedDependencyCandidateEvidence(Base):
    __tablename__ = "delivery_dependency_candidate_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            [
                "delivery_dependency_candidates.tenant_id",
                "delivery_dependency_candidates.id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )


class DeliveryEvidence(Base):
    __tablename__ = "delivery_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dependency_id: Mapped[str | None] = mapped_column(String(36))
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "source_system", "source_record_id", "content_hash"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "milestone_id"],
            ["delivery_milestones.tenant_id", "delivery_milestones.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_delivery_evidence_tenant_entity",
            "tenant_id",
            "entity_type",
            "entity_id",
        ),
        Index("ix_delivery_evidence_tenant_captured", "tenant_id", "captured_at"),
    )


class DeliveryRecommendation(Base):
    __tablename__ = "delivery_recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dependency_id: Mapped[str | None] = mapped_column(String(36))
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    raid_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "milestone_id"],
            ["delivery_milestones.tenant_id", "delivery_milestones.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_recommendation_tenant_status", "tenant_id", "status"),
    )


class ProposedAction(Base):
    __tablename__ = "delivery_proposed_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(36))
    message_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    response_id: Mapped[str | None] = mapped_column(String(36))
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    work_item_id: Mapped[str | None] = mapped_column(String(36))
    dependency_id: Mapped[str | None] = mapped_column(String(36))
    recommendation_id: Mapped[str | None] = mapped_column(String(36))
    raid_id: Mapped[str | None] = mapped_column(String(36))
    trace_id: Mapped[str | None] = mapped_column(String(80))
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(30), default="USER", nullable=False)
    requester_id: Mapped[str | None] = mapped_column(String(255))
    agent_id: Mapped[str | None] = mapped_column(String(160))
    target_entity_type: Mapped[str | None] = mapped_column(String(50))
    target_entity_id: Mapped[str | None] = mapped_column(String(36))
    target_system: Mapped[str] = mapped_column(
        String(80), default="INTERNAL", nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    original_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    target: Mapped[str | None] = mapped_column(String(255))
    owner_id: Mapped[str | None] = mapped_column(String(255))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    risk_classification: Mapped[str] = mapped_column(
        String(30), default="CONTROLLED", nullable=False
    )
    risk_level: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    policy_id: Mapped[str | None] = mapped_column(String(36))
    policy_version: Mapped[int | None] = mapped_column(Integer)
    approval_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    required_approval_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_action_tenant_idempotency"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "response_id"],
            ["delivery_copilot_responses.tenant_id", "delivery_copilot_responses.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_item_id"],
            ["delivery_work_items.tenant_id", "delivery_work_items.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "recommendation_id"],
            ["delivery_recommendations.tenant_id", "delivery_recommendations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_proposed_action_tenant_status", "tenant_id", "status"),
        Index("ix_proposed_action_tenant_owner", "tenant_id", "owner_id"),
        Index("ix_proposed_action_tenant_response", "tenant_id", "response_id"),
        Index("ix_proposed_action_tenant_raid", "tenant_id", "raid_id"),
        Index("ix_action_tenant_requester", "tenant_id", "requester_id"),
        Index("ix_action_tenant_risk_status", "tenant_id", "risk_level", "status"),
        Index("ix_action_tenant_expiration", "tenant_id", "expires_at"),
        Index(
            "ix_action_tenant_target",
            "tenant_id",
            "target_entity_type",
            "target_entity_id",
        ),
    )


class DeliveryRAIDEvidence(Base):
    __tablename__ = "delivery_raid_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    raid_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    linked_by: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_raid_evidence_tenant_evidence", "tenant_id", "evidence_id"),
    )


class DeliveryRAIDRelationship(Base):
    __tablename__ = "delivery_raid_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    raid_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        String(40), default="AFFECTS", nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "raid_id", "entity_type", "entity_id", "relationship_type"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        Index("ix_raid_relationship_entity", "tenant_id", "entity_type", "entity_id"),
    )


class DeliveryRAIDRelatedItem(Base):
    __tablename__ = "delivery_raid_related_items"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    raid_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    related_raid_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(
        String(40), default="RELATED", nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "related_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("raid_id <> related_raid_id", name="ck_raid_not_self_related"),
    )


class DeliveryRAIDHistory(Base):
    __tablename__ = "delivery_raid_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    raid_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    change_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        Index("ix_raid_history_tenant_item", "tenant_id", "raid_id", "changed_at"),
    )


class DeliveryRAIDReview(Base):
    __tablename__ = "delivery_raid_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    raid_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    next_review_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        Index("ix_raid_review_tenant_item", "tenant_id", "raid_id", "reviewed_at"),
    )


class DetectedRAIDCandidate(Base):
    __tablename__ = "delivery_raid_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    affected_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    suggested_owner: Mapped[str | None] = mapped_column(String(255))
    suggested_due_date: Mapped[date | None] = mapped_column(Date)
    suggested_probability: Mapped[str | None] = mapped_column(String(30))
    suggested_impact: Mapped[str | None] = mapped_column(String(30))
    possible_duplicates: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    limitations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    detected_by_agent: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissal_reason: Mapped[str | None] = mapped_column(Text)
    accepted_raid_id: Mapped[str | None] = mapped_column(String(36))
    merged_raid_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "trace_id"),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "merged_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_raid_candidate_tenant_status", "tenant_id", "status", "detected_at"),
    )


class DetectedRAIDCandidateEvidence(Base):
    __tablename__ = "delivery_raid_candidate_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            ["delivery_raid_candidates.tenant_id", "delivery_raid_candidates.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )


class DeliveryCopilotResponse(Base):
    __tablename__ = "delivery_copilot_responses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    user_message_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    assistant_message_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), nullable=False
    )
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    raid_id: Mapped[str | None] = mapped_column(String(36))
    dependency_id: Mapped[str | None] = mapped_column(String(36))
    response_type: Mapped[str] = mapped_column(
        String(30), default="SPRINT_INTELLIGENCE", nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "trace_id"),
        ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["user_message_id"], ["messages.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["assistant_message_id"], ["messages.id"], ondelete="RESTRICT"
        ),
        Index(
            "ix_copilot_response_tenant_conversation", "tenant_id", "conversation_id"
        ),
    )


class CopilotResponseEvidence(Base):
    __tablename__ = "delivery_copilot_response_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    response_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "response_id"],
            ["delivery_copilot_responses.tenant_id", "delivery_copilot_responses.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )


class CopilotFeedback(Base):
    __tablename__ = "delivery_copilot_feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_id: Mapped[str] = mapped_column(String(80), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(80))
    feedback_type: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        Index("ix_feedback_tenant_conversation", "tenant_id", "conversation_id"),
    )


class ConversationDeliveryContext(Base):
    __tablename__ = "conversation_delivery_contexts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "conversation_id", "entity_type", "entity_id"),
        Index("ix_context_tenant_conversation", "tenant_id", "conversation_id"),
    )


class RecommendationEvidence(Base):
    __tablename__ = "delivery_recommendation_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "recommendation_id"],
            ["delivery_recommendations.tenant_id", "delivery_recommendations.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )


class ProposedActionEvidence(Base):
    __tablename__ = "delivery_proposed_action_evidence"
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    proposed_action_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )
