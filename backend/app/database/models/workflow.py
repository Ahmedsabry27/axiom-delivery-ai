from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("tenant_id", "public_id", name="uq_workflow_tenant_public"),
        Index("ix_workflows_tenant_status", "tenant_id", "lifecycle_status"),
        Index("ix_workflows_tenant_owner", "tenant_id", "owner_id"),
        Index("ix_workflows_tenant_updated", "tenant_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), default="default", index=True)

    goal: Mapped[str]

    description: Mapped[str | None] = mapped_column(nullable=True)

    assigned_agent: Mapped[str | None] = mapped_column(nullable=True)

    trigger_type: Mapped[str] = mapped_column(default="MANUAL")

    definition: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(
        default="CREATED",
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", index=True
    )
    owner_id: Mapped[str] = mapped_column(String(160), default="system")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1)

    created_by: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    updated_by: Mapped[str] = mapped_column(String(160), default="system")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
        Index(
            "ix_workflow_versions_tenant_workflow",
            "tenant_id",
            "workflow_id",
            "version",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(40), default="MANUAL", nullable=False
    )
    validation_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkflowActivityEvent(Base):
    __tablename__ = "workflow_activity_events"
    __table_args__ = (
        Index(
            "ix_workflow_activity_tenant_workflow",
            "tenant_id",
            "workflow_id",
            "created_at",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    workflow_version: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class WorkflowAccessGrant(Base):
    __tablename__ = "workflow_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_workflow_access_grant",
        ),
        Index(
            "ix_workflow_access_subject",
            "tenant_id",
            "subject_type",
            "subject_id",
            "action",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
