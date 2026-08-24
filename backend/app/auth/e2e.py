"""Signed, short-lived identities for isolated browser tests only."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


class E2EAuthenticationError(ValueError):
    """Raised when the isolated E2E credential is unavailable or invalid."""


def _max_lifetime_seconds() -> int:
    """Return the isolated test-token lifetime, bounded to two hours."""
    try:
        configured = int(os.getenv("E2E_AUTH_MAX_LIFETIME_SECONDS", "900"))
    except ValueError as error:
        raise E2EAuthenticationError(
            "E2E_AUTH_MAX_LIFETIME_SECONDS must be an integer"
        ) from error
    return min(max(configured, 1), 7200)


def _enabled() -> bool:
    return os.getenv("E2E_AUTH_ENABLED", "").lower() == "true"


def validate_e2e_environment() -> None:
    environment = os.getenv("APP_ENV", "development").lower()
    if _enabled() and environment not in {"test", "e2e", "ci", "local"}:
        raise RuntimeError(
            "E2E authentication is forbidden outside isolated test environments"
        )
    if _enabled() and len(os.getenv("E2E_AUTH_SECRET", "")) < 32:
        raise RuntimeError("E2E_AUTH_SECRET must contain at least 32 characters")


def verify_e2e_token(token: str) -> dict[str, Any]:
    validate_e2e_environment()
    if not _enabled() or not token.startswith("e2e."):
        raise E2EAuthenticationError("E2E authentication is disabled")
    try:
        _, encoded, supplied_signature = token.split(".", 2)
        secret = os.environ["E2E_AUTH_SECRET"].encode()
        expected_signature = hmac.new(
            secret, encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise E2EAuthenticationError("Invalid E2E credential signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise E2EAuthenticationError("Malformed E2E credential") from error
    if claims.get("iss") != "ai-delivery-platform-e2e":
        raise E2EAuthenticationError("Invalid E2E credential issuer")
    now = int(time.time())
    max_lifetime = _max_lifetime_seconds()
    issued_at = int(claims.get("iat", 0))
    expires_at = int(claims.get("exp", 0))
    if not now - max_lifetime <= issued_at <= now + 30:
        raise E2EAuthenticationError("Invalid E2E credential issue time")
    if not now < expires_at <= issued_at + max_lifetime:
        raise E2EAuthenticationError("Expired or overlong E2E credential")
    if not claims.get("sub") or not claims.get("custom:tenant_id"):
        raise E2EAuthenticationError("Incomplete E2E identity")
    return claims


def issue_e2e_token(claims: dict[str, Any], lifetime_seconds: int = 300) -> str:
    """Issue a credential from trusted test setup code, never from an HTTP route."""
    validate_e2e_environment()
    if not _enabled():
        raise E2EAuthenticationError("E2E authentication is disabled")
    now = int(time.time())
    payload = {
        **claims,
        "iss": "ai-delivery-platform-e2e",
        "iat": now,
        "exp": now + min(max(lifetime_seconds, 1), _max_lifetime_seconds()),
    }
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(
        os.environ["E2E_AUTH_SECRET"].encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"e2e.{encoded}.{signature}"
