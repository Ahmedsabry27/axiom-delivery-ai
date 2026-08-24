"""Run Alembic without reflecting credential-bearing exception strings."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config

from alembic import command

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security.sanitization import sanitize_text


def main() -> int:
    operation = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    revision = sys.argv[2] if len(sys.argv) > 2 else "head"
    try:
        config = Config("alembic.ini")
        if operation == "upgrade":
            command.upgrade(config, revision)
        elif operation == "stamp":
            command.stamp(config, revision)
        else:
            raise ValueError("Operation must be upgrade or stamp")
    except Exception as exc:  # noqa: BLE001 -- security boundary for CLI diagnostics
        print(f"Migration failed: {sanitize_text(str(exc))}", file=sys.stderr)
        return 1
    print(f"Migration operation completed: {operation} {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
