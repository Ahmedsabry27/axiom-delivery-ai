from app.database.base import Base
from app.database.postgres import (
    SessionLocal,
    engine,
    get_db,
)

# Import all models so SQLAlchemy registers them
from app.models.conversation import Conversation as Conversation
from app.models.message import Message as Message


def init_db():
    Base.metadata.create_all(bind=engine)


__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
]
