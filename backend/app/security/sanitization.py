"""Public-error and log sanitization for credentials and connection strings."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<userinfo>[^/@\s]+)@",
    re.IGNORECASE,
)
_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*([^\s,;]+)"
)
_LIBPQ_PASSWORD = re.compile(r"(?i)(\bpassword=)(?:'[^']*'|\S+)")


def sanitize_text(value: object) -> str:
    """Return text with URL userinfo and common secret fields removed."""

    text = str(value)
    text = _URL_CREDENTIALS.sub(r"\g<scheme>" + REDACTED + "@", text)
    text = _KEY_VALUE_SECRET.sub(lambda match: f"{match.group(1)}={REDACTED}", text)
    return _LIBPQ_PASSWORD.sub(r"\1" + REDACTED, text)


def sanitize_value(value: Any) -> Any:
    """Recursively sanitize values before they enter structured logs."""

    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {
            key: REDACTED
            if any(
                marker in str(key).lower()
                for marker in (
                    "password",
                    "secret",
                    "token",
                    "authorization",
                    "api_key",
                )
            )
            else sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def public_error(
    _: BaseException, message: str = "The request could not be completed"
) -> str:
    """Create a stable public error without reflecting exception internals."""

    return message
