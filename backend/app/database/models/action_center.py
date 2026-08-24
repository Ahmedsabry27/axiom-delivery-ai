from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ApprovalDecision(Base):
    __tablename__ = "action_approval_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    proposed_action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    evidence_snapshot: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVED','REJECTED','CHANGES_REQUESTED')",
            name="ck_action_decision_value",
        ),
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "approval_request_id",
            "action_version",
            "actor_id",
            name="uq_action_decision_actor_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        Index(
            "ix_action_decision_tenant_action",
            "tenant_id",
            "proposed_action_id",
            "created_at",
        ),
    )


class ActionExecution(Base):
    __tablename__ = "action_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    proposed_action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    executed_by: Mapped[str] = mapped_column(String(160), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "status IN ('EXECUTING','EXECUTED','FAILED','PARTIALLY_EXECUTED')",
            name="ck_action_execution_status",
        ),
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "proposed_action_id",
            "idempotency_key",
            name="uq_execution_idempotency",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        Index("ix_execution_tenant_status", "tenant_id", "status", "started_at"),
        Index("ix_execution_tenant_trace", "tenant_id", "trace_id"),
    )


class ActionVerification(Base):
    __tablename__ = "action_verifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False)
    verification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    assigned_verifier_id: Mapped[str | None] = mapped_column(String(160))
    verified_by: Mapped[str | None] = mapped_column(String(160))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    observed_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','VERIFIED','VERIFICATION_FAILED')",
            name="ck_action_verification_status",
        ),
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "execution_id"),
        ForeignKeyConstraint(
            ["tenant_id", "execution_id"],
            ["action_executions.tenant_id", "action_executions.id"],
            ondelete="CASCADE",
        ),
        Index("ix_verification_tenant_status", "tenant_id", "status"),
    )


class ActionPolicyDefinition(Base):
    __tablename__ = "action_policy_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    approval_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    verification_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    execution_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','RETIRED')",
            name="ck_action_policy_status",
        ),
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "action_type", "version"),
        Index("ix_policy_tenant_active", "tenant_id", "action_type", "status"),
    )


class ActionNotification(Base):
    __tablename__ = "action_notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    proposed_action_id: Mapped[str | None] = mapped_column(String(36))
    approval_request_id: Mapped[str | None] = mapped_column(String(36))
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    route: Mapped[str] = mapped_column(String(500), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            ondelete="CASCADE",
        ),
        Index("ix_notification_tenant_user_read", "tenant_id", "user_id", "read"),
    )


@event.listens_for(ApprovalDecision, "before_update")
@event.listens_for(ApprovalDecision, "before_delete")
def _prevent_approval_decision_mutation(*_args) -> None:
    raise ValueError("Approval decisions are append-only")
