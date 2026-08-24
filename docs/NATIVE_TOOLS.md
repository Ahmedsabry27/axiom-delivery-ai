# Sprint 12 Native Enterprise Tools

Sprint 12 extends the Sprint 11 registry and executor; it does not create a parallel runtime. Native operations therefore inherit JSON Schema validation, Cognito permission checks, tenant context, timeouts, idempotency, redaction, execution records, metrics, agent discovery, and correlation IDs.

## File Tool

`file_upload`, `file_read`, `file_extract`, `file_summarize`, and `file_search` support PDF, DOCX, TXT, Markdown, CSV, XLSX, PPTX, and JSON. Uploads normalize names, validate content signatures, cap size, checksum/deduplicate per tenant, scan through a replaceable scanner boundary (the built-in scanner rejects the EICAR signature), store tenant-scoped objects, extract text, and index tenant-scoped chunks. Production storage should be an encrypted mounted volume or replaceable object-store adapter. Summaries currently use deterministic extractive summarization; connect the approved model abstraction before enabling generative summaries.

## Database Tool

Connections persist safe metadata and secret references. Runtime URLs are injected as `NATIVE_DB_URL_<NORMALIZED_CONNECTION_ID>`. `sqlglot` parses every query; only one comment-free `SELECT`/`UNION` is accepted, tables must be allowlisted, mutations are rejected, and a limit is injected. PostgreSQL sessions use read-only transactions. Use a dedicated read-only database role in production.

## REST API Tool

Profiles define an HTTPS base URL, regex path allowlist, method allowlist, timeout, and response limit. URL parsing, DNS/IP checks, forbidden-network rejection, dangerous-header removal, disabled redirects, method permissions, response truncation, and header sanitization apply before results enter audit history. Tokens are injected as `NATIVE_REST_TOKEN_<NORMALIZED_CONNECTION_ID>` and never returned.

## Notification Tool

Email, Teams, and internal alerts use narrow permissions and idempotency keys. External email, large recipient groups, critical severity, and Teams broadcasts enter `pending_approval`; an administrator with `notifications.approve` completes delivery. HTML is stripped and provider IDs are safe. The built-in provider records internal delivery; production email/Graph transports remain replaceable and require live credentials.

## Permissions

Files: `files.upload`, `files.read`, `files.extract`, `files.summarize`, `files.search`. Database: `database.connections.read`, `database.connections.manage`, `database.query`. REST: `api.connections.read`, `api.connections.manage`, `api.invoke`, `api.invoke.write`. Notifications: `notifications.email.send`, `notifications.teams.send`, `notifications.alert.create`, `notifications.approve`, `notifications.history.read`.

Apply `alembic upgrade head`, configure `.env.example`, run `pytest -q tests/test_native_tools.py`, and open `/native-tools`. Normal CI uses fake/local resources and requires no cloud credentials.
