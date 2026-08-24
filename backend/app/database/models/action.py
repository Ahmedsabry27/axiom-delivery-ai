from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str]

    tenant_id: Mapped[str] = mapped_column(String(120), default="default", index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    integration_connection_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)

    type: Mapped[str]

    permissions: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )
    status: Mapped[str] = mapped_column(default="ENABLED")
    usage: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
