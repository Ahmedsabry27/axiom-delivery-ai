from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_phase2_schema_and_existing_knowledge_migration(tmp_path, monkeypatch):
    database = tmp_path / "agent-phase2.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "c2d4e6f8a0b1")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO knowledge_sources "
                "(name, source_type, location, created_at) "
                "VALUES ('Legacy source', 'DOCUMENT', NULL, CURRENT_TIMESTAMP)"
            )
        )

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {
        "agent_tool_assignments",
        "agent_knowledge_assignments",
        "agent_access_assignments",
        "agent_execution_settings",
    } <= set(inspector.get_table_names())
    knowledge_columns = {
        item["name"] for item in inspector.get_columns("knowledge_sources")
    }
    assert {
        "tenant_id",
        "owner_id",
        "readiness_status",
        "health_status",
        "last_synchronized_at",
    } <= knowledge_columns
    with engine.connect() as connection:
        migrated = connection.execute(
            text(
                "SELECT tenant_id, owner_id, readiness_status, health_status "
                "FROM knowledge_sources WHERE name='Legacy source'"
            )
        ).one()
    assert migrated == ("default", "system", "pending", "unknown")

    command.downgrade(config, "c2d4e6f8a0b1")
    assert "agent_tool_assignments" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "agent_tool_assignments" in inspect(engine).get_table_names()
