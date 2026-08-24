from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text


def expected_heads() -> set[str]:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def current_revisions(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version"))
        return {str(row[0]) for row in rows}


def require_current_schema(engine: Engine) -> None:
    try:
        current = current_revisions(engine)
    except Exception as exc:
        raise RuntimeError("Database migration state is unavailable") from exc
    expected = expected_heads()
    if current != expected:
        raise RuntimeError(
            "Database schema is not at the required migration head; run migrations before startup"
        )
