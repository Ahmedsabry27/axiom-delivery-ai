from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_phase3_forward_and_round_trip(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'phase3.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "d3e5f7a9b1c2")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO conversations (id,title,user_id,created_at,updated_at) VALUES ('00000000000000000000000000000001','Legacy','legacy',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {"agent_executions", "agent_continuations"} <= set(
        inspector.get_table_names()
    )
    assert {"tenant_id", "agent_uuid", "agent_version"} <= {
        column["name"] for column in inspector.get_columns("conversations")
    }
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT tenant_id,title FROM conversations WHERE user_id='legacy'")
        ).one() == ("default", "Legacy")
    command.downgrade(config, "d3e5f7a9b1c2")
    assert "agent_executions" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "agent_continuations" in inspect(engine).get_table_names()
