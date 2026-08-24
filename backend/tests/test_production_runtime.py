from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.database.config import _secure_configured_url
from app.database.migrations import require_current_schema


def production_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "DATABASE_SECRET_ARN": "arn:aws:secretsmanager:region:account:secret:test",
        "CORS_ALLOWED_ORIGINS": "https://app.example.com",
        "COGNITO_REGION": "us-east-1",
        "COGNITO_USER_POOL_ID": "pool",
        "COGNITO_CLIENT_ID": "client",
        "OPENAI_API_KEY": "injected-test-value",
        "BUDGET_ENFORCEMENT_ENABLED": True,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_are_fail_closed():
    settings = production_settings()
    assert settings.production
    assert settings.cors_origins == ["https://app.example.com"]
    with pytest.raises(ValidationError):
        production_settings(CORS_ALLOWED_ORIGINS="")
    with pytest.raises(ValidationError):
        production_settings(RUN_SCHEMA_CREATE=True)
    with pytest.raises(ValidationError):
        production_settings(OPENAI_API_KEY=None)
    with pytest.raises(ValidationError):
        production_settings(BUDGET_ENFORCEMENT_ENABLED=False)


def test_production_database_requires_tls_and_rejects_sqlite(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    url = _secure_configured_url("postgresql+psycopg://user:pass@db.example/app")
    assert "sslmode=require" in url
    with pytest.raises(RuntimeError, match="SQLite"):
        _secure_configured_url("sqlite:///unsafe.db")


def test_startup_rejects_database_behind_migration_head():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        )
        connection.execute(text("INSERT INTO alembic_version VALUES ('outdated')"))
    with pytest.raises(RuntimeError, match="migration head"):
        require_current_schema(engine)
