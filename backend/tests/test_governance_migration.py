from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_governance_migration_clean_and_from_previous_head(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'governance.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "b2d4f6a8c0e1")
    engine = create_engine(url)
    assert "governance_policies" not in inspect(engine).get_table_names()

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {
        "governance_policies",
        "governance_access_reviews",
        "governed_models",
        "model_prices",
        "ai_usage_records",
        "ai_budgets",
        "evaluation_datasets",
        "evaluation_runs",
        "evaluation_results",
        "ai_incidents",
        "retention_policies",
        "budget_reservations",
        "budget_alerts",
        "budget_overrides",
    } <= set(inspector.get_table_names())
    assert {
        "event_id",
        "trace_id",
        "previous_hash",
        "integrity_hash",
        "canonical_payload",
    } <= {column["name"] for column in inspector.get_columns("audit_logs")}
    assert "state_version" in {
        column["name"] for column in inspector.get_columns("ai_budgets")
    }

    command.downgrade(config, "b2d4f6a8c0e1")
    assert "governance_policies" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "governance_policies" in inspect(engine).get_table_names()
