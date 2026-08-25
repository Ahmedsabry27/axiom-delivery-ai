import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.metrics.metrics import (
    db_connection_errors,
    db_queries_total,
    db_query_latency_seconds,
)
from app.models.conversation import Conversation


class ConversationRepository:
    # --------------------------------------------------
    # Create
    # --------------------------------------------------

    def create(
        self,
        db: Session,
        user_id: str,
        title: str,
        tenant_id: str = "default",
    ) -> Conversation:

        start = time.perf_counter()

        try:
            conversation = Conversation(
                title=title,
                user_id=user_id,
                tenant_id=tenant_id,
            )

            db.add(conversation)
            db.commit()
            db.refresh(conversation)

            return conversation

        except Exception:
            db.rollback()
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    # --------------------------------------------------
    # Read
    # --------------------------------------------------

    def get_all(
        self,
        db: Session,
        user_id: str,
        tenant_id: str | None = None,
    ) -> list[Conversation]:

        start = time.perf_counter()

        try:
            return (
                db.query(Conversation)
                .filter(
                    Conversation.user_id == user_id,
                    *([Conversation.tenant_id == tenant_id] if tenant_id else []),
                )
                .order_by(Conversation.updated_at.desc())
                .all()
            )

        except Exception:
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    def get_by_id(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ) -> Conversation | None:

        start = time.perf_counter()

        try:
            return (
                db.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                    *([Conversation.tenant_id == tenant_id] if tenant_id else []),
                )
                .first()
            )

        except Exception:
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    # --------------------------------------------------
    # Update Title
    # --------------------------------------------------

    def update_title(
        self,
        db: Session,
        conversation: Conversation,
        title: str,
    ) -> Conversation:

        start = time.perf_counter()

        try:
            conversation.title = title
            conversation.updated_at = datetime.now(UTC)

            db.commit()
            db.refresh(conversation)

            return conversation

        except Exception:
            db.rollback()
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    def update(
        self,
        db: Session,
        conversation: Conversation,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
        context_summary: dict | None = None,
    ) -> Conversation:
        if title is not None:
            conversation.title = title.strip()[:255] or "New Conversation"
        if is_pinned is not None:
            conversation.is_pinned = is_pinned
        if is_archived is not None:
            conversation.is_archived = is_archived
        if context_summary is not None:
            conversation.context_summary = context_summary
        conversation.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(conversation)
        return conversation

    # --------------------------------------------------
    # Touch Conversation
    # --------------------------------------------------

    def touch(
        self,
        db: Session,
        conversation: Conversation,
    ) -> Conversation:

        start = time.perf_counter()

        try:
            conversation.updated_at = datetime.now(UTC)

            db.commit()
            db.refresh(conversation)

            return conversation

        except Exception:
            db.rollback()
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    # --------------------------------------------------
    # Delete
    # --------------------------------------------------

    def delete(
        self,
        db: Session,
        conversation: Conversation,
    ) -> bool:

        start = time.perf_counter()

        try:
            db.delete(conversation)
            db.commit()

            return True

        except Exception:
            db.rollback()
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)


conversation_repository = ConversationRepository()
