from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class Agent(Base):
    """Canonical persisted agent aggregate.

    ``id`` remains an internal compatibility key. ``uuid`` is the stable external
    identity used by the versioned API and runtime cache.
    """

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agent_tenant_slug"),
        CheckConstraint(
            "lifecycle_status IN ('draft','published','enabled','disabled','archived','error')",
            name="ck_agent_lifecycle_status",
        ),
        Index("ix_agents_tenant_status", "tenant_id", "lifecycle_status"),
        Index("ix_agents_tenant_owner", "tenant_id", "owner_id"),
        Index("ix_agents_tenant_updated", "tenant_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(120), nullable=False, default="default", index=True
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False, default="system")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    operational_health: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unknown"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_configuration_ref: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    planner_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    instruction_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tool_discovery_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="assigned_only"
    )
    memory_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    max_execution_steps: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    execution_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120
    )
    cost_limit: Mapped[float | None] = mapped_column(nullable=True)
    risk_limit: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    environment_restrictions: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    configuration: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )
    created_by: Mapped[str] = mapped_column(
        String(160), nullable=False, default="system"
    )
    updated_by: Mapped[str] = mapped_column(
        String(160), nullable=False, default="system"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[str | None] = mapped_column(String(160))

    # Compatibility aliases used by legacy screens while they migrate to v1.
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    health: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")

    versions: Mapped[list[AgentVersion]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_version"),
        Index("ix_agent_versions_tenant_agent", "tenant_id", "agent_id", "version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    planner_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    memory_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    execution_limits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tool_discovery_configuration: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    configuration_snapshot: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    change_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    agent: Mapped[Agent] = relationship(back_populates="versions")


class AgentActivityEvent(Base):
    __tablename__ = "agent_activity_events"
    __table_args__ = (
        Index("ix_agent_activity_tenant_agent", "tenant_id", "agent_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    agent_version: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


@event.listens_for(Agent, "before_insert")
def _populate_legacy_agent_identity(_mapper, _connection, target: Agent) -> None:
    """Keep old constructors safe while callers migrate to AgentApplicationService."""
    if not target.uuid:
        target.uuid = str(uuid4())
    if not target.slug:
        normalized = "-".join(
            part for part in target.name.lower().replace("_", "-").split("-") if part
        )
        target.slug = (normalized or f"agent-{target.uuid[:8]}")[:120]
