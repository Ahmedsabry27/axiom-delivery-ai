from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid4())


class AgentToolAssignment(Base):
    __tablename__ = "agent_tool_assignments"
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "tool_name", "assignment_action", name="uq_agent_tool_action"
        ),
        CheckConstraint(
            "assignment_action IN ('execute','discover')",
            name="ck_agent_tool_action",
        ),
        CheckConstraint(
            "risk_mode IN ('read','write','destructive')",
            name="ck_agent_tool_risk",
        ),
        Index("ix_agent_tools_tenant_agent", "tenant_id", "agent_id", "enabled"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_version: Mapped[int | None] = mapped_column(Integer)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version_restriction: Mapped[str | None] = mapped_column(String(80))
    assignment_action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="execute"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    risk_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    added_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class AgentKnowledgeAssignment(Base):
    __tablename__ = "agent_knowledge_assignments"
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "knowledge_source_id", name="uq_agent_knowledge_source"
        ),
        CheckConstraint(
            "access_mode IN ('read','search','retrieve')",
            name="ck_agent_knowledge_access",
        ),
        Index("ix_agent_knowledge_tenant_agent", "tenant_id", "agent_id", "enabled"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    knowledge_source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    readiness_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class AgentAccessAssignment(Base):
    __tablename__ = "agent_access_assignments"
    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_agent_access_subject_action",
        ),
        CheckConstraint(
            "subject_type IN ('user','group','role','service')",
            name="ck_agent_access_subject_type",
        ),
        CheckConstraint(
            "action IN ('view','edit','publish','execute','manage_tools','manage_knowledge','manage_access','view_executions','view_analytics')",
            name="ck_agent_access_action",
        ),
        Index("ix_agent_access_lookup", "tenant_id", "agent_id", "subject_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class AgentExecutionSetting(Base):
    __tablename__ = "agent_execution_settings"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_execution_setting"),
        Index("ix_agent_execution_settings_tenant", "tenant_id", "agent_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    cost_limit: Mapped[float | None] = mapped_column()
    risk_limit: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    updated_by: Mapped[str] = mapped_column(String(160), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )
