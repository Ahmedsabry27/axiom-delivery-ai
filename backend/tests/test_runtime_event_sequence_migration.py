from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_runtime_sequence_counter_backfills_actual_maximum(tmp_path, monkeypatch):
    database = tmp_path / "runtime-sequence-migration.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "f8d1b6c3e540")
    engine = create_engine(url)
    empty_id, gap_id = uuid4().hex, uuid4().hex
    with engine.begin() as connection:
        for execution_id in (empty_id, gap_id):
            connection.execute(
                text(
                    "INSERT INTO runtime_executions "
                    "(id, conversation_id, workflow_id, user_id, tenant_id, status, "
                    "state_version, next_event_sequence, attempt, steps, runtime_metadata, "
                    "token_usage) VALUES "
                    "(:id, :conversation_id, :workflow_id, 'user', 'tenant', 'RUNNING', "
                    "0, 1, 1, '[]', '{}', '{}')"
                ),
                {
                    "id": execution_id,
                    "conversation_id": uuid4().hex,
                    "workflow_id": uuid4().hex,
                },
            )
        for sequence in (2, 7):
            connection.execute(
                text(
                    "INSERT INTO runtime_execution_events "
                    "(id, execution_id, sequence, event_type, state_version, final, payload, created_at) "
                    "VALUES (:id, :execution_id, :sequence, 'step', 0, 0, '{}', CURRENT_TIMESTAMP)"
                ),
                {"id": uuid4().hex, "execution_id": gap_id, "sequence": sequence},
            )

    command.upgrade(config, "head")
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("runtime_executions")
    }
    assert columns["last_event_sequence"]["nullable"] is False
    with engine.connect() as connection:
        counters = dict(
            connection.execute(
                text(
                    "SELECT id, last_event_sequence FROM runtime_executions "
                    "WHERE id IN (:empty_id, :gap_id)"
                ),
                {"empty_id": empty_id, "gap_id": gap_id},
            ).all()
        )
    assert counters[empty_id] == 0
    assert counters[gap_id] == 7
