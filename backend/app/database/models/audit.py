from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    tenant_id: Mapped[str | None]

    user_id: Mapped[str | None]

    event_type: Mapped[str]

    entity: Mapped[str]

    entity_id: Mapped[str]

    timestamp: Mapped[datetime]

    actor_id: Mapped[str | None]
    action: Mapped[str | None]
    target_type: Mapped[str | None]
    target_id: Mapped[str | None]
    correlation_id: Mapped[str | None]
    before_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(80), index=True)
    actor_type: Mapped[str | None] = mapped_column(String(20))
    result: Mapped[str | None] = mapped_column(String(30), index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36))
    policy_version: Mapped[int | None] = mapped_column(Integer)
    agent_id: Mapped[str | None] = mapped_column(String(36))
    model_id: Mapped[str | None] = mapped_column(String(36))
    provider: Mapped[str | None] = mapped_column(String(80))
    tool_id: Mapped[str | None] = mapped_column(String(120))
    execution_id: Mapped[str | None] = mapped_column(String(36), index=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), index=True)
    severity: Mapped[str | None] = mapped_column(String(20), index=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    integrity_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    canonical_payload: Mapped[str | None] = mapped_column(Text)


@event.listens_for(AuditLog, "before_update")
@event.listens_for(AuditLog, "before_delete")
def _prevent_audit_mutation(*_args) -> None:
    raise ValueError("Audit events are append-only")
