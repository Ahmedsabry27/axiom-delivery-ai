from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.config import database_url

# --------------------------------------------------
# Load environment
# --------------------------------------------------

load_dotenv()


DATABASE_URL = database_url()


# --------------------------------------------------
# SQLAlchemy Engine
# --------------------------------------------------

_engine_options: dict = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DATABASE_POOL_RECYCLE_SECONDS", "300")),
    "hide_parameters": True,
}
if DATABASE_URL.startswith("sqlite"):
    _engine_options.pop("pool_recycle", None)
    _engine_options["connect_args"] = {"check_same_thread": False}
    if DATABASE_URL.endswith(":memory:"):
        _engine_options["poolclass"] = StaticPool
else:
    _engine_options.update(
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
        pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT_SECONDS", "30")),
    )

engine = create_engine(DATABASE_URL, **_engine_options)


# --------------------------------------------------
# Session Factory
# --------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# --------------------------------------------------
# FastAPI Dependency
# --------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    Provide database session.

    Usage:

    db: Session = Depends(get_db)
    """

    db: Session = SessionLocal()

    try:
        yield db

    finally:
        db.close()
