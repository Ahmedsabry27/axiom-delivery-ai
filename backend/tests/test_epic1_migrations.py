from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_fresh_migration_allows_multiple_events_per_execution(tmp_path: Path) -> None:
    database = tmp_path / "epic1-migrations.db"
    backend = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+pysqlite:///{database}",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    with sqlite3.connect(database) as connection:
        indexes = {
            row[1]: row
            for row in connection.execute("PRAGMA index_list(runtime_execution_events)")
        }
        terminal = indexes["uq_runtime_events_terminal"]
        # SQLite PRAGMA index_list column 4 identifies a partial index. Without
        # this predicate, execution_id accidentally becomes globally unique and
        # the normal second lifecycle event fails on freshly migrated databases.
        assert terminal[4] == 1
