from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    workflow_id: Mapped[int]

    name: Mapped[str]

    status: Mapped[str] = mapped_column(
        default="PENDING",
    )

    # Agent is assigned during workflow execution,
    # not necessarily when task is created.
    agent: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
