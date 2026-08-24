from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.mcp_integration.errors import MCPAuthenticationFailed
from app.mcp_integration.security import resolve_secret


class OAuthStateStore:
    """Short-lived PKCE state. Tokens remain in the configured external secret store."""

    def __init__(self):
        self._states: dict[str, dict] = {}

    def create(self, server_id: str, actor_id: str) -> tuple[str, str, str]:
        self.purge()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        self._states[state] = {
            "server_id": server_id,
            "actor_id": actor_id,
            "verifier": verifier,
            "expires": time.time() + 600,
        }
        return state, verifier, challenge

    def consume(self, state: str, server_id: str, actor_id: str) -> str:
        item = self._states.pop(state, None)
        if (
            not item
            or item["expires"] < time.time()
            or item["server_id"] != server_id
            or item["actor_id"] != actor_id
        ):
            raise MCPAuthenticationFailed("OAuth state is invalid or expired")
        return item["verifier"]

    def purge(self):
        now = time.time()
        self._states = {
            key: value for key, value in self._states.items() if value["expires"] >= now
        }


oauth_states = OAuthStateStore()


def authorization_url(server, actor_id: str) -> str:
    config = server.auth_config or {}
    required = ("authorization_url", "client_id", "redirect_uri")
    if any(not config.get(key) for key in required):
        raise MCPAuthenticationFailed("OAuth configuration is incomplete")
    state, _, challenge = oauth_states.create(server.id, actor_id)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": " ".join(server.requested_scopes or []),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{config['authorization_url']}?{query}"


async def exchange_code(server, actor_id: str, state: str, code: str) -> dict:
    config = server.auth_config or {}
    verifier = oauth_states.consume(state, server.id, actor_id)
    secret = resolve_secret(config.get("client_secret_reference"))
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": config.get("client_id"),
        "redirect_uri": config.get("redirect_uri"),
        "code_verifier": verifier,
    }
    if secret:
        payload["client_secret"] = secret
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(config["token_url"], data=payload)
            response.raise_for_status()
            token = response.json()
    except Exception as exc:
        raise MCPAuthenticationFailed("OAuth token exchange failed") from exc
    # Deliberately never persist or return bearer/refresh tokens. Deployments write the
    # token into the secret reference configured on the server using their secret store.
    return {
        "token_type": token.get("token_type", "Bearer"),
        "expires_in": token.get("expires_in"),
        "scope": token.get("scope", "").split(),
        "secret_reference_required": not bool(server.secret_reference),
    }
