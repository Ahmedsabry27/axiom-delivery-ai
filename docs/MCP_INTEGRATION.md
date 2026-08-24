# Sprint 13 — Model Context Protocol integration

The platform uses the official Python MCP SDK, pinned to version 1.28.1.
Streamable HTTP is primary and SSE is retained for explicitly configured legacy
servers. Servers, capabilities, and sync history are tenant-scoped. Credential
values are never persisted; configuration contains only env:// references.

## Administration flow

1. Register a public HTTPS endpoint in **MCP Servers**.
2. Select no auth, API key, JWT, service-account token, or OAuth 2.0 with PKCE.
3. Test the handshake and protocol negotiation.
4. Synchronize tools, resources, resource templates, and prompts.
5. Review and explicitly approve capabilities. New tools default to disabled.
6. Execute approved tools through the existing Tool Executor. Its validation,
   authorization, timeouts, audit history, correlation IDs, and bounds apply.

Discovery fingerprints schemas and descriptions. Changed tools are disabled and
returned to review; missing capabilities remain as disabled audit records.
Provider metadata and all provider output are treated as untrusted content.

## Security configuration

- HTTPS is mandatory, redirects are disabled, hosts are allowlisted, and DNS
  resolution rejects private, loopback, link-local, and reserved addresses.
- MCP_ALLOW_PRIVATE_NETWORK=true is only for controlled local integration tests.
- MCP_MAX_SCHEMA_BYTES defaults to 65,536 bytes. Schema depth, request/response
  sizes, timeouts, and concurrency are bounded.
- OAuth PKCE state is single-use and expires after ten minutes. The callback
  never returns or stores access or refresh tokens; production secret-store
  automation writes them to the configured secret reference.

## Verification

Run from the repository root:

    cd backend && .venv/bin/alembic upgrade head
    backend/.venv/bin/pytest -q backend/tests/test_mcp_integration.py
    backend/.venv/bin/pytest -q
    backend/.venv/bin/mypy backend/app/mcp_integration backend/app/api/mcp.py
    backend/.venv/bin/ruff check backend/app/mcp_integration backend/app/api/mcp.py
    cd frontend && npm test && npm run lint && npm run build

The fake_mcp_server.py test module defines a standards-compliant FastMCP
provider with a tool, static resource, resource template, and prompt.
