from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_empty_database_upgrade_to_sprint_head(tmp_path, monkeypatch):
    database = tmp_path / "migrations.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(url)).get_table_names())
    assert {
        "tool_definitions",
        "tool_executions",
        "integration_configurations",
        "native_files",
        "native_file_contents",
        "native_connections",
        "native_notifications",
        "mcp_servers",
        "mcp_capabilities",
        "mcp_sync_runs",
        "tool_search_index",
        "tool_marketplace_profiles",
        "tool_assignments",
        "tool_governance_policies",
        "tool_discovery_events",
        "tool_candidate_decisions",
        "tool_discovery_feedback",
        "approval_requests",
        "clarification_requests",
    } <= tables


def test_sprint_head_round_trip(tmp_path, monkeypatch):
    database = tmp_path / "round-trip.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")
    command.downgrade(config, "f9a1b3c5d7e9")
    command.upgrade(config, "head")

    inspector = inspect(create_engine(url))
    assert "tool_search_index" in inspector.get_table_names()
    assert {"uq_governance_policy_version"} <= {
        item["name"]
        for item in inspector.get_unique_constraints("tool_governance_policies")
    }
