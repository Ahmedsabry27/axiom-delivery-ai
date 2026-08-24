from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now():
    return datetime.now(UTC)


class NativeFile(Base):
    __tablename__ = "native_files"
    __table_args__ = (
        UniqueConstraint("tenant_id", "checksum", name="uq_native_file_checksum"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    normalized_filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(120))
    extension: Mapped[str] = mapped_column(String(20))
    byte_size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    owner_id: Mapped[str] = mapped_column(String(160), index=True)
    scan_status: Mapped[str] = mapped_column(String(30), default="safe")
    processing_status: Mapped[str] = mapped_column(
        String(30), default="uploaded", index=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extractor_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class NativeFileContent(Base):
    __tablename__ = "native_file_contents"
    __table_args__ = (
        UniqueConstraint("file_id", "sequence", name="uq_native_file_content_sequence"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("native_files.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    character_count: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class NativeConnection(Base):
    __tablename__ = "native_connections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kind", "display_name", name="uq_native_connection"
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    engine: Mapped[str | None] = mapped_column(String(40), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safe_config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(160))
    updated_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class NativeNotification(Base):
    __tablename__ = "native_notifications"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "channel",
            "idempotency_key",
            name="uq_native_notification_idempotency",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str] = mapped_column(String(160))
    recipient_summary: Mapped[dict] = mapped_column(JSON)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    safe_message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    approval_state: Mapped[str] = mapped_column(String(30), default="not_required")
    provider_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
