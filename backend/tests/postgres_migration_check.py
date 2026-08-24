"""Disposable PostgreSQL migration round-trip and schema assertions."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.database.models  # noqa: F401
from alembic import command
from app.database.base import Base
from app.database.config import database_url


def main() -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(database_url())
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required = {
        "approval_requests",
        "clarification_requests",
        "audit_logs",
        "mcp_capabilities",
    }
    assert required <= tables, required - tables
    assert "uq_mcp_capability_tenant_internal" in {
        item["name"] for item in inspector.get_unique_constraints("mcp_capabilities")
    }
    model_tables = set(Base.metadata.tables)
    assert model_tables <= tables, model_tables - tables
    command.downgrade(config, "a0b2c4d6e8f1")
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
