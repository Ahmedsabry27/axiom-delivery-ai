from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    engine_from_config,
    event,
    pool,
)

from alembic import context
from app.database import models as database_models  # noqa: F401
from app.database.config import database_url

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env")


DATABASE_URL = database_url()


# --------------------------------------------------
# Alembic Config
# --------------------------------------------------

config = context.config


config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL.replace("%", "%%"),
)


if config.config_file_name is not None:
    # Migration commands run in-process during tests. Preserve application
    # loggers so Alembic cannot disable redaction/audit logging globally.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


# --------------------------------------------------
# Import SQLAlchemy Metadata
# --------------------------------------------------

from app.database.base import Base  # noqa: E402 -- application path is configured above

# Import all database models
# Required so Alembic can detect tables

target_metadata = Base.metadata


# --------------------------------------------------
# Offline Migration
# --------------------------------------------------


def run_migrations_offline() -> None:

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------
# Online Migration
# --------------------------------------------------


def run_migrations_online() -> None:

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Historical data migrations use lightweight ``sa.table`` objects for
    # JSON payloads. Psycopg 3 requires an explicit dumper when those columns
    # have no SQLAlchemy type metadata. Register it only on migration
    # connections; application model-bound JSON handling remains unchanged.
    if (
        connectable.dialect.name == "postgresql"
        and connectable.dialect.driver == "psycopg"
    ):
        from psycopg.types.json import JsonDumper

        @event.listens_for(connectable, "connect")
        def register_migration_json_dumper(dbapi_connection, _connection_record):
            dbapi_connection.adapters.register_dumper(dict, JsonDumper)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# --------------------------------------------------
# Entry Point
# --------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()

else:
    run_migrations_online()
