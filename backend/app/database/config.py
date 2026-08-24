from __future__ import annotations

import json
import os

import boto3  # type: ignore[import-untyped]
from sqlalchemy import URL, make_url


def _secure_configured_url(configured: str) -> str:
    environment = os.getenv("APP_ENV", "development").lower()
    if environment not in {"production", "prod"}:
        return configured
    parsed = make_url(configured)
    if parsed.drivername.startswith("sqlite"):
        raise RuntimeError("SQLite is forbidden as the production database")
    if parsed.drivername.startswith("postgresql"):
        query = dict(parsed.query)
        query.setdefault("sslmode", "require")
        parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False)


def database_url() -> str:
    """Resolve a database URL without persisting or logging database credentials."""
    secret_arn = os.getenv("DATABASE_SECRET_ARN")
    if secret_arn:
        region = os.getenv("AWS_REGION", "us-east-1")
        response = boto3.client("secretsmanager", region_name=region).get_secret_value(
            SecretId=secret_arn
        )
        try:
            value = json.loads(response["SecretString"])
            required = {"username", "password"}
            if not required <= value.keys():
                raise ValueError("Database secret does not contain required fields")
            host = os.getenv("DATABASE_HOST") or value.get("host")
            port = os.getenv("DATABASE_PORT") or value.get("port") or 5432
            if not host:
                raise ValueError("DATABASE_HOST is required for this database secret")
            return URL.create(
                "postgresql+psycopg",
                username=value["username"],
                password=value["password"],
                host=host,
                port=int(port),
                database=value.get("dbname")
                or os.getenv("DATABASE_NAME")
                or "postgres",
                query={"sslmode": "require"},
            ).render_as_string(hide_password=False)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Database secret has an invalid format") from exc
    configured = os.getenv("DATABASE_URL")
    if not configured:
        raise RuntimeError("DATABASE_SECRET_ARN or DATABASE_URL is required")
    return _secure_configured_url(configured)
