from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), default="default", index=True)
    owner_id: Mapped[str] = mapped_column(String(160), default="system")
    name: Mapped[str] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(default="DOCUMENT")
    location: Mapped[str | None] = mapped_column(nullable=True)
    readiness_status: Mapped[str] = mapped_column(String(30), default="pending")
    health_status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_synchronized_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
