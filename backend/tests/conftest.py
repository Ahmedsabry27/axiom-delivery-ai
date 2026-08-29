# ruff: noqa: E402

import os
import tempfile
from pathlib import Path

test_database_path = Path(tempfile.gettempdir()) / (
    f"ai_delivery_platform_tests_{os.getpid()}.db"
)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{test_database_path.as_posix()}"
os.environ["TRUSTED_HOSTS"] = ""
os.environ["RUN_SCHEMA_CREATE"] = "false"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.registry import AgentRegistry
from app.database import models as database_models  # noqa: F401
from app.database.base import Base
from app.database.session import engine as application_engine
from app.runtime.event_bus import EventBus

# --------------------------------------------------
# Existing Runtime Fixtures
# --------------------------------------------------


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def agent_registry():
    return AgentRegistry()


@pytest.fixture(autouse=True)
def application_database_schema():
    """Keep application-level API tests isolated from production infrastructure."""

    Base.metadata.create_all(bind=application_engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=application_engine)


# --------------------------------------------------
# Database Test Configuration
# --------------------------------------------------

# SQLite in-memory database for tests
# Production uses AWS PostgreSQL

TEST_DATABASE_URL = "sqlite:///:memory:"


engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# --------------------------------------------------
# Database Session Fixture
# --------------------------------------------------


@pytest.fixture
def db_session():

    # Create tables before test

    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()

    try:
        yield session

    finally:
        session.close()

        # Clean database after test

        Base.metadata.drop_all(bind=engine)
