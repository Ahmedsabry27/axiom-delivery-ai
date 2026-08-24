import io
import logging

from fastapi.testclient import TestClient

from app.logging.logger import logger
from app.main import app
from app.security.sanitization import REDACTED, sanitize_text

SENSITIVE_DSN = "postgresql://example_user:example_password@db.example.test/app"


def test_sanitize_text_removes_complete_database_credentials():
    result = sanitize_text(
        f"connection failed: {SENSITIVE_DSN} password=example_password"
    )

    assert "example_password" not in result
    assert "example_user" not in result
    assert SENSITIVE_DSN not in result
    assert REDACTED in result


def test_application_logger_redacts_exception_traceback():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logger.handlers[0].formatter)
    logger.addHandler(handler)
    try:
        try:
            raise RuntimeError(f"database unavailable: {SENSITIVE_DSN}")
        except RuntimeError:
            logger.exception("database operation failed")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "example_password" not in output
    assert "example_user" not in output
    assert SENSITIVE_DSN not in output
    assert REDACTED in output


def test_authentication_error_does_not_reflect_verifier_exception(monkeypatch):
    def fail_verification(_token):
        raise RuntimeError(f"verifier configuration: {SENSITIVE_DSN}")

    monkeypatch.setattr("app.auth.dependencies.verify_token", fail_verification)
    response = TestClient(app).get(
        "/api/v1/tools", headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired bearer token"}
    assert "example_password" not in response.text
    assert SENSITIVE_DSN not in response.text
