from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    email: Mapped[str] = mapped_column(
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        default="USER",
    )

    tenant_id: Mapped[str] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
