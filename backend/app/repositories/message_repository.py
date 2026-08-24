import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.metrics.metrics import (
    db_connection_errors,
    db_queries_total,
    db_query_latency_seconds,
)
from app.models.message import Message


class MessageRepository:
    def create(
        self,
        db: Session,
        conversation_id: UUID,
        role: str,
        content: str,
        response_id: str | None = None,
    ) -> Message:

        start = time.perf_counter()

        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                response_id=response_id,
            )

            db.add(message)
            db.commit()
            db.refresh(message)

            return message

        except Exception:
            db.rollback()
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)

    def get_by_conversation(
        self,
        db: Session,
        conversation_id: UUID,
    ) -> list[Message]:

        start = time.perf_counter()

        try:
            return (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .all()
            )

        except Exception:
            db_connection_errors.inc()
            raise

        finally:
            db_queries_total.inc()
            db_query_latency_seconds.observe(time.perf_counter() - start)


message_repository = MessageRepository()
