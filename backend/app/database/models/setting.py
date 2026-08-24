from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SettingValue(Base):
    __tablename__ = "setting_values"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_by: Mapped[str] = mapped_column(String(160), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "scope", "key", name="uq_setting_scope_key"
        ),
        Index("ix_setting_tenant_scope", "tenant_id", "scope"),
    )


class SettingVersion(Base):
    __tablename__ = "setting_versions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    setting_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(500))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    changed_by: Mapped[str] = mapped_column(String(160), nullable=False)
