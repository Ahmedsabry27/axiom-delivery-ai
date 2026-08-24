import time

import pytest

from app.auth.e2e import E2EAuthenticationError, issue_e2e_token, verify_e2e_token

SECRET = "phase-four-browser-test-secret-is-long-enough"


def configure(monkeypatch, environment="e2e"):
    monkeypatch.setenv("E2E_AUTH_ENABLED", "true")
    monkeypatch.setenv("E2E_AUTH_SECRET", SECRET)
    monkeypatch.setenv("APP_ENV", environment)


def test_signed_short_lived_e2e_identity(monkeypatch):
    configure(monkeypatch)
    token = issue_e2e_token(
        {
            "sub": "admin",
            "custom:tenant_id": "e2e-tenant",
            "permissions": ["agents.admin"],
        }
    )
    assert verify_e2e_token(token)["sub"] == "admin"


def test_e2e_auth_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("E2E_AUTH_ENABLED", raising=False)
    with pytest.raises(E2EAuthenticationError):
        verify_e2e_token("e2e.payload.signature")


def test_e2e_auth_refuses_production(monkeypatch):
    configure(monkeypatch, "production")
    with pytest.raises(RuntimeError, match="forbidden"):
        issue_e2e_token({"sub": "admin", "custom:tenant_id": "e2e-tenant"})


def test_tampering_and_overlong_credentials_are_rejected(monkeypatch):
    configure(monkeypatch)
    token = issue_e2e_token({"sub": "viewer", "custom:tenant_id": "e2e-tenant"})
    with pytest.raises(E2EAuthenticationError):
        verify_e2e_token(token + "tampered")
    monkeypatch.setattr(time, "time", lambda: 1)
    with pytest.raises(E2EAuthenticationError):
        verify_e2e_token(token)


def test_isolated_ci_can_extend_token_lifetime(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("E2E_AUTH_MAX_LIFETIME_SECONDS", "3600")
    issued_at = int(time.time())
    token = issue_e2e_token(
        {"sub": "admin", "custom:tenant_id": "e2e-tenant"},
        lifetime_seconds=3600,
    )
    monkeypatch.setattr(time, "time", lambda: issued_at + 120)
    assert verify_e2e_token(token)["sub"] == "admin"
