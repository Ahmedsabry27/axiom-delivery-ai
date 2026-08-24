from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_dependency_migration_preserves_existing_data_and_round_trips(
    tmp_path, monkeypatch
):
    database = tmp_path / "dependency-migration.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "d6b9f4e1a327")
    engine = create_engine(url)
    common = "id,tenant_id,name,status,source_system,created_at,updated_at,version,record_metadata"
    values = "(:id,'tenant-a',:name,'ACTIVE','MANUAL',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1,'{}')"
    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO delivery_portfolios ({common}) VALUES {values}"),
            {"id": "portfolio", "name": "Synthetic Portfolio"},
        )
        connection.execute(
            text(
                f"INSERT INTO delivery_programmes ({common},portfolio_id) VALUES ({values[1:-1]},'portfolio')"
            ),
            {"id": "programme", "name": "Synthetic Programme"},
        )
        connection.execute(
            text(
                f"INSERT INTO delivery_projects ({common},programme_id) VALUES ({values[1:-1]},'programme')"
            ),
            {"id": "project", "name": "Synthetic Project"},
        )
        connection.execute(
            text(
                f"INSERT INTO delivery_dependencies ({common},project_id,description,dependency_type,impact,priority,required_by_date,identified_at,critical_path) VALUES ({values[1:-1]},'project','Legacy dependency','TECHNICAL','HIGH','HIGH',NULL,CURRENT_TIMESTAMP,0)"
            ),
            {"id": "legacy-dependency", "name": "Legacy Dependency"},
        )
    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {
        "delivery_dependency_history",
        "delivery_dependency_scenarios",
        "delivery_dependency_candidates",
    } <= set(inspector.get_table_names())
    columns = {
        column["name"] for column in inspector.get_columns("delivery_dependencies")
    }
    assert {
        "reference",
        "relationship_type",
        "forecast_resolution_date",
        "acknowledged_at",
        "external",
    } <= columns
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT reference FROM delivery_dependencies WHERE id='legacy-dependency'"
                )
            )
            == "D-legacy-d"
        )
    command.downgrade(config, "d6b9f4e1a327")
    assert "reference" not in {
        column["name"]
        for column in inspect(engine).get_columns("delivery_dependencies")
    }
    command.upgrade(config, "head")
    assert "reference" in {
        column["name"]
        for column in inspect(engine).get_columns("delivery_dependencies")
    }
