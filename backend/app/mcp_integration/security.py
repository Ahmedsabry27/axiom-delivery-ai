from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlparse

from app.mcp_integration.errors import MCPAuthenticationFailed, UnsafeMCPServerURL

SLUG = re.compile(r"^[a-z][a-z0-9_]{1,78}[a-z0-9]$")


def normalize_slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80]
    if not SLUG.fullmatch(value):
        raise ValueError("slug must normalize to 3-80 lower-case characters")
    return value


def normalize_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80]
    if not value or not value[0].isalpha():
        value = "tool_" + value
    return value


def validate_server_url(url: str, allowed_hosts: list[str], *, resolve_dns=True) -> str:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https" or p.username or p.password or not host:
        raise UnsafeMCPServerURL("MCP servers must use credential-free HTTPS URLs")
    if allowed_hosts and host not in {x.lower() for x in allowed_hosts}:
        raise UnsafeMCPServerURL("MCP server host is not allowlisted")
    if resolve_dns:
        try:
            addresses = {
                ipaddress.ip_address(x[4][0])
                for x in socket.getaddrinfo(host, p.port or 443)
            }
        except OSError as exc:
            raise UnsafeMCPServerURL("MCP server host could not be resolved") from exc
        if os.getenv("MCP_ALLOW_PRIVATE_NETWORK", "false").lower() != "true" and any(
            x.is_private or x.is_loopback or x.is_link_local or x.is_reserved
            for x in addresses
        ):
            raise UnsafeMCPServerURL("MCP server resolves to a forbidden network")
    return p.geturl()


def resolve_secret(reference: str | None) -> str | None:
    if not reference:
        return None
    if not reference.startswith("env://"):
        raise MCPAuthenticationFailed(
            "Only configured secret-store references are supported"
        )
    value = os.getenv(reference[6:])
    if not value:
        raise MCPAuthenticationFailed("MCP credential is not available")
    return value


def fingerprint(data) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def schema_depth(value, depth=0):
    if depth > 12:
        raise ValueError("MCP schema exceeds maximum depth")
    if isinstance(value, dict):
        for child in value.values():
            schema_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            schema_depth(child, depth + 1)


def normalize_schema(schema: dict) -> dict:
    if not isinstance(schema, dict) or schema.get("type", "object") != "object":
        raise ValueError("MCP tool schema root must be an object")
    if len(json.dumps(schema)) > int(os.getenv("MCP_MAX_SCHEMA_BYTES", "65536")):
        raise ValueError("MCP schema exceeds maximum size")
    schema_depth(schema)
    result = json.loads(json.dumps(schema))
    result.setdefault("type", "object")
    result.setdefault("properties", {})
    result.setdefault("additionalProperties", False)
    return result


def sanitize_text(value, max_length=2000):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))[:max_length]
