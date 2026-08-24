from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

from app.mcp_integration.errors import MCPConnectionFailed, MCPResponseTooLarge
from app.mcp_integration.security import resolve_secret, validate_server_url

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, server):
        self.server = server
        self.stack = None
        self.session = None
        self.initialized = None

    def _headers(self):
        secret = resolve_secret(self.server.secret_reference)
        kind = self.server.auth_type
        cfg = self.server.auth_config or {}
        if kind == "none":
            return {}
        if not secret:
            return {}
        if kind == "api_key":
            return {
                cfg.get(
                    "header_name", "Authorization"
                ): f"{cfg.get('prefix', 'Bearer')} {secret}".strip()
            }
        if kind in {"jwt", "service_account", "oauth2"}:
            return {"Authorization": f"Bearer {secret}"}
        return {}

    async def connect(self):
        policy = self.server.policy or {}
        url = validate_server_url(
            self.server.server_url, policy.get("allowed_hosts", [])
        )
        headers = self._headers()
        timeout = min(policy.get("connection_timeout", 10), 30)
        self.stack = AsyncExitStack()
        try:
            if self.server.transport == "sse":
                read, write = await self.stack.enter_async_context(
                    sse_client(
                        url,
                        headers=headers,
                        timeout=timeout,
                        sse_read_timeout=policy.get("request_timeout", 30),
                    )
                )
            else:
                client = httpx.AsyncClient(
                    headers=headers,
                    timeout=httpx.Timeout(
                        policy.get("request_timeout", 30), connect=timeout
                    ),
                    follow_redirects=False,
                    verify=True,
                )
                read, write, _ = await self.stack.enter_async_context(
                    streamable_http_client(url, http_client=client)
                )
            self.session = await self.stack.enter_async_context(
                ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(
                        seconds=policy.get("request_timeout", 30)
                    ),
                    client_info=Implementation(
                        name="ai-delivery-platform", version="1.3.0"
                    ),
                )
            )
            self.initialized = await self.session.initialize()
            return self.initialized
        except Exception as exc:
            await self.disconnect()
            raise MCPConnectionFailed("Could not initialize the MCP server") from exc

    async def disconnect(self):
        if self.stack:
            try:
                await self.stack.aclose()
            except Exception:  # noqa: BLE001 -- context managers may wrap transport-specific errors
                logger.exception("Failed to close MCP client transport")
        self.stack = None
        self.session = None

    async def ping(self):
        await self.session.send_ping()
        return True

    async def list_tools(self):
        return (await self.session.list_tools()).tools

    async def call_tool(self, name, args):
        return await self.session.call_tool(name, args)

    async def list_resources(self):
        return (await self.session.list_resources()).resources

    async def read_resource(self, uri):
        return await self.session.read_resource(uri)

    async def list_resource_templates(self):
        return (await self.session.list_resource_templates()).resourceTemplates

    async def list_prompts(self):
        return (await self.session.list_prompts()).prompts

    async def get_prompt(self, name, args):
        return await self.session.get_prompt(name, args)

    def bounded(self, value):
        raw = json.dumps(
            value,
            default=lambda x: (
                x.model_dump(mode="json") if hasattr(x, "model_dump") else str(x)
            ),
        )
        limit = min(
            (self.server.policy or {}).get("max_response_bytes", 1_000_000), 5_000_000
        )
        if len(raw.encode()) > limit:
            raise MCPResponseTooLarge("MCP response exceeded the configured limit")
        return json.loads(raw)


class MCPClientManager:
    def __init__(self, client_factory=MCPClient):
        self.client_factory = client_factory
        self._locks = {}
        self._semaphores = {}

    @asynccontextmanager
    async def session(self, server):
        semaphore = self._semaphores.setdefault(
            server.id,
            asyncio.Semaphore(
                min((server.policy or {}).get("concurrency_limit", 4), 20)
            ),
        )
        async with semaphore:
            client = self.client_factory(server)
            await client.connect()
            try:
                yield client
            finally:
                await client.disconnect()


manager = MCPClientManager()
