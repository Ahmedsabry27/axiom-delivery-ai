from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid4())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("resume_token_hash", name="uq_approval_resume_token"),
        UniqueConstraint("tenant_id", "id", name="uq_approval_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        Index("ix_approval_tenant_status", "tenant_id", "status", "created_at"),
        Index("ix_approval_binding", "tenant_id", "tool_name", "tool_version"),
        Index(
            "ix_action_approval_assignee",
            "tenant_id",
            "assigned_approver_id",
            "status",
        ),
        Index(
            "ix_action_approval_action",
            "tenant_id",
            "proposed_action_id",
            "action_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    proposed_action_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(40), nullable=False)
    discovery_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    requester_id: Mapped[str] = mapped_column(String(160), nullable=False)
    requester_agent_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_approver_role: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    required_approver_group: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    assigned_approver_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    assigned_role: Mapped[str | None] = mapped_column(String(160), nullable=True)
    required_approval_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    delegated_from: Mapped[str | None] = mapped_column(String(160), nullable=True)
    delegated_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    separation_of_duties: Mapped[bool] = mapped_column(default=True)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    safe_action_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    approver_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resume_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    audit_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __mapper_args__: ClassVar[dict] = {"version_id_col": state_version}


class ClarificationRequest(Base):
    __tablename__ = "clarification_requests"
    __table_args__ = (
        UniqueConstraint("resume_token_hash", name="uq_clarification_resume_token"),
        Index("ix_clarification_tenant_status", "tenant_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    discovery_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_alternatives: Mapped[list] = mapped_column(JSON, default=list)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    known_values: Mapped[dict] = mapped_column(JSON, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="waiting_for_input")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    user_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requester_id: Mapped[str] = mapped_column(String(160), nullable=False)
    audit_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __mapper_args__: ClassVar[dict] = {"version_id_col": state_version}
