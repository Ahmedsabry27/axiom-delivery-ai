import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # NEW: Cognito user identifier (JWT "sub")
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(120), nullable=False, default="default", index=True
    )
    agent_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agent_version: Mapped[int | None] = mapped_column(nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
