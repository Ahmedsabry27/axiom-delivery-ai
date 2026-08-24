"""add atomic runtime event metadata and sequence allocation

Revision ID: f2b4d6e8a0c3
Revises: e1a3c5d7f9b2
Create Date: 2026-08-12
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "f2b4d6e8a0c3"
down_revision: str | Sequence[str] | None = "e1a3c5d7f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runtime_executions",
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "runtime_executions",
        sa.Column(
            "next_event_sequence", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("aggregate_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("component_type", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("component_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("component_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "runtime_execution_events",
        sa.Column("final", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    bind = op.get_bind()
    terminal_types = {
        "COMPLETED": "runtime.completed",
        "FAILED": "runtime.failed",
        "CANCELLED": "runtime.cancelled",
        "TIMED_OUT": "runtime.timed_out",
    }
    terminal_rows = bind.execute(
        sa.text(
            "SELECT id, workflow_id, status, completed_at, duration_ms, "
            "result_message, error FROM runtime_executions "
            "WHERE status IN ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT')"
        )
    ).mappings()
    for row in terminal_rows:
        sequence = bind.execute(
            sa.text(
                "SELECT COALESCE(MAX(sequence), 0) + 1 "
                "FROM runtime_execution_events WHERE execution_id = :execution_id"
            ),
            {"execution_id": row["id"]},
        ).scalar_one()
        event_type = terminal_types[row["status"]]
        occurred_at = row["completed_at"] or datetime.now(UTC).replace(tzinfo=None)
        payload = {
            "event_id": None,
            "execution_id": str(row["id"]),
            "workflow_id": str(row["workflow_id"]),
            "sequence": sequence,
            "state_version": 0,
            "type": event_type,
            "name": "Result Generated"
            if row["status"] == "COMPLETED"
            else "Runtime Execution",
            "description": row["error"] or f"Runtime execution {row['status'].lower()}",
            "status": row["status"].lower(),
            "aggregate_status": row["status"],
            "component_type": "runtime",
            "component_id": str(row["id"]),
            "component_status": row["status"],
            "duration_ms": row["duration_ms"],
            "message": row["result_message"],
            "error": row["error"],
            "timestamp": occurred_at.isoformat(),
            "final": True,
            "step_id": "result-generated"
            if row["status"] == "COMPLETED"
            else "runtime-execution",
        }
        event_id = uuid.uuid4()
        payload["event_id"] = str(event_id)
        bind.execute(
            sa.text(
                "INSERT INTO runtime_execution_events "
                "(id, execution_id, sequence, event_type, state_version, aggregate_status, "
                "component_type, component_id, component_status, final, name, status, "
                "description, payload, created_at) VALUES "
                "(:id, :execution_id, :sequence, :event_type, 0, :aggregate_status, "
                "'runtime', :component_id, :component_status, true, :name, :status, "
                ":description, CAST(:payload AS JSON), :created_at)"
            ),
            {
                "id": event_id,
                "execution_id": row["id"],
                "sequence": sequence,
                "event_type": event_type,
                "aggregate_status": row["status"],
                "component_id": str(row["id"]),
                "component_status": row["status"],
                "name": payload["name"],
                "status": payload["status"],
                "description": payload["description"],
                "payload": json.dumps(payload),
                "created_at": occurred_at,
            },
        )
    op.execute(
        "UPDATE runtime_executions AS execution "
        "SET next_event_sequence = COALESCE(("
        "SELECT MAX(event.sequence) + 1 FROM runtime_execution_events AS event "
        "WHERE event.execution_id = execution.id), 1)"
    )
    op.create_index(
        "ix_runtime_events_execution_final",
        "runtime_execution_events",
        ["execution_id", "final"],
        unique=False,
    )
    op.create_index(
        "uq_runtime_events_terminal",
        "runtime_execution_events",
        ["execution_id"],
        unique=True,
        postgresql_where=sa.text("final = true AND component_type = 'runtime'"),
        sqlite_where=sa.text("final = 1 AND component_type = 'runtime'"),
    )


def downgrade() -> None:
    op.drop_index("uq_runtime_events_terminal", table_name="runtime_execution_events")
    op.drop_index(
        "ix_runtime_events_execution_final", table_name="runtime_execution_events"
    )
    op.drop_column("runtime_execution_events", "final")
    op.drop_column("runtime_execution_events", "component_status")
    op.drop_column("runtime_execution_events", "component_id")
    op.drop_column("runtime_execution_events", "component_type")
    op.drop_column("runtime_execution_events", "aggregate_status")
    op.drop_column("runtime_execution_events", "state_version")
    op.drop_column("runtime_executions", "next_event_sequence")
    op.drop_column("runtime_executions", "state_version")
