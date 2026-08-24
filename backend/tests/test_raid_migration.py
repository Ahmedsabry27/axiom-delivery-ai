from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_upgrade_from_axh03_preserves_legacy_raid_and_round_trips(
    tmp_path, monkeypatch
):
    database = tmp_path / "raid-migration.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "c5a8e3d0f216")
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
                f"INSERT INTO delivery_raid_items ({common},project_id,item_type,impact,probability) VALUES ({values[1:-1]},'project','RISK','HIGH','LIKELY')"
            ),
            {"id": "legacy-risk", "name": "Legacy risk"},
        )
    assert "reference" not in {
        column["name"] for column in inspect(engine).get_columns("delivery_raid_items")
    }

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {
        "delivery_raid_history",
        "delivery_raid_candidates",
        "delivery_raid_evidence",
        "delivery_raid_relationships",
    } <= set(inspector.get_table_names())
    columns = {
        column["name"] for column in inspector.get_columns("delivery_raid_items")
    }
    assert {
        "reference",
        "attention_score",
        "residual_exposure_score",
        "validation_owner_id",
        "decision_owner_id",
    } <= columns
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT reference FROM delivery_raid_items WHERE id='legacy-risk'")
            )
            == "LEGACY-legacy-risk"
        )

    command.downgrade(config, "c5a8e3d0f216")
    assert "reference" not in {
        column["name"] for column in inspect(engine).get_columns("delivery_raid_items")
    }
    command.upgrade(config, "head")
    assert "reference" in {
        column["name"] for column in inspect(engine).get_columns("delivery_raid_items")
    }
