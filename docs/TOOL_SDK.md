# Tool SDK Foundation

## Architecture and lifecycle

Sprint 11 keeps executable Python objects in the process and persists their safe administrative metadata. This prevents database content from becoming executable code while still making enablement, configuration summaries, version state, and history durable.

The runtime path is: authenticated caller → `ToolExecutor` → version resolution → enabled/permission checks → JSON Schema validation/defaults → audit row → timeout/retry policy → adapter/tool → output validation/redaction → telemetry and normalized envelope. Agents use `app.tool_sdk.agent`; they cannot call implementations directly.

Stable public modules are `app.tool_sdk`, `app.contracts.tool`, and `app.contracts.tool_models`. Adapter and built-in-tool modules are application internals and may evolve.

## Package layout

- `app/contracts/tool.py`: async `Tool` base contract.
- `app/contracts/tool_models.py`: immutable metadata, execution context, result, error, and retry types.
- `app/tool_sdk/registry.py`: deterministic, version-aware runtime registry.
- `app/tool_sdk/executor.py`: authorized execution, timeout/retry, audit, redaction, and metrics.
- `app/tool_sdk/adapters.py`: ServiceNow, Microsoft Graph, local file, Azure Blob, and Key Vault adapters.
- `app/tool_sdk/builtin_tools.py`: read-only Sprint 11 tools.
- `app/api/tools.py`: versioned catalog, administration, execution, history, and configuration API.
- `app/database/models/tool.py`: persistent definitions, executions, and integration summaries.

## Implementing a tool

```python
from app.tool_sdk import ExecutionContext, Tool, ToolMetadata, ToolResult

class DeploymentReportTool(Tool):
    metadata = ToolMetadata(
        name="deployment_report",
        display_name="Deployment Report",
        description="Return a deployment summary",
        category="devops",
        provider="internal",
        version="1.0.0",
        permissions=("deployments.read",),
        parameters={
            "type": "object",
            "properties": {"environment": {"type": "string", "maxLength": 80}},
            "required": ["environment"],
            "additionalProperties": False,
        },
    )

    async def execute(self, input_data: dict, context: ExecutionContext) -> ToolResult:
        return ToolResult.succeeded({"environment": input_data["environment"], "status": "healthy"})
```

Register explicitly during application composition: `registry.register(DeploymentReportTool())`. Duplicate name/version pairs fail startup. New compatible behavior gets a patch/minor version; breaking input/output changes get a major version. The highest explicitly active version is resolved when no version is requested. Deprecated versions remain addressable until removed by a migration/release.

## Metadata and validation

Names use lower snake case and versions use Semantic Versioning. Parameters and optional outputs are JSON Schema Draft 2020-12. Schemas are capped at 64 KB and 100 top-level properties, must reject additional properties, and cannot expose credential-like parameters. Inputs are capped at 256 KB and output summaries at 1 MB. Provider pagination is bounded to 100 items.

## Permissions and security

The API derives permissions from Cognito scopes/claims. Members of the `admin`, `administrators`, or `platform-admin` group receive `tools.admin`; other identities only see and execute tools for which all required permissions are present. Administrative endpoints require `tools.admin`. Every query and history lookup is tenant-scoped using `custom:tenant_id` (default `default`).

Local files are restricted to canonical approved roots, reject traversal and symlink escape, allow only configured text extensions, enforce size limits, and require UTF-8. Configurable provider endpoints require public HTTPS URLs and do not follow redirects. ServiceNow table/field access is allowlisted and result size is bounded. Azure containers are allowlisted. The public Key Vault tool returns metadata only—never secret values. Arbitrary SQL, shell, code upload, and unrestricted HTTP execution are not part of this SDK.

Integration responses never include `secret_reference`; they only expose `credential_configured`. Secret values must live in the platform secret manager or deployment environment. Tokens, passwords, authorization headers, keys, cookies, signed URLs, and connection strings are recursively redacted from execution records.

## Built-in tools

- ServiceNow: `servicenow_incident_search`, `servicenow_incident_get`, `servicenow_change_search`, `servicenow_asset_search`.
- Files: `file_list`, `file_metadata`, `file_read`.
- Azure: `azure_blob_list`, `azure_blob_metadata`, `azure_blob_read`, `azure_keyvault_secret_metadata`.
- SharePoint/OneDrive: `MicrosoftGraphAdapter` provides the common Graph file transport for provider-specific tools without duplicating authentication/error behavior.

All Sprint 11 tools are read-only. Provider errors are normalized as `INTEGRATION_NOT_CONFIGURED`, `INTEGRATION_UNAVAILABLE`, or `RATE_LIMITED` without exposing raw bodies.

## API

- `GET /api/v1/tools`, `/tools/{name}`, `/tools/{name}/versions`, `/tools/categories`, `/tools/providers`
- `POST /api/v1/tools/{name}/execute` (`Idempotency-Key` and `X-Correlation-ID` supported)
- `PATCH /api/v1/tools/{name}/{version}/enabled?enabled=true`
- `GET /api/v1/tool-executions`, `/tool-executions/{id}`
- `GET /api/v1/integrations`
- `PUT /api/v1/integrations/{provider}` and `POST /api/v1/integrations/{provider}/verify`

Example:

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/v1/tools
curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"input":{"query":"state=1","limit":10}}' \
  http://localhost:8000/api/v1/tools/servicenow_incident_search/execute
```

Errors use stable codes: `TOOL_NOT_FOUND`, `TOOL_VERSION_NOT_FOUND`, `TOOL_DISABLED`, `INVALID_TOOL_INPUT`, `OUTPUT_VALIDATION_FAILED`, `PERMISSION_DENIED`, `INTEGRATION_NOT_CONFIGURED`, `INTEGRATION_UNAVAILABLE`, `EXECUTION_TIMEOUT`, `EXECUTION_CANCELLED`, `RATE_LIMITED`, `UNSAFE_OPERATION_REJECTED`, and `TOOL_EXECUTION_FAILED`.

## Configuration and deployment

Copy `.env.example` and configure only the providers required in that environment. Optional integrations do not prevent startup. Prefer managed/workload identity; access-token variables support local development and should be populated by a secret injector, never committed. ServiceNow requires an approved instance and read scopes. Graph requires tenant/client identity and least-privilege Sites/Files scopes. Blob requires an endpoint and container allowlist. Key Vault requires metadata/list permission only. Restart workers after changing injected secrets.

Run `alembic upgrade head` before deploying. The migration creates indexed `tool_definitions`, `tool_executions`, and `integration_configurations`; rollback is `alembic downgrade c6e8f0a2b4d6`.

## Testing and troubleshooting

Run `pytest -q tests/test_tool_sdk.py tests/test_tool_api.py`, then the complete backend suite and `npm run build`. Tests use SQLite and fake adapters and require no cloud credentials. A 424 means configuration is absent; 403 means the Cognito token lacks a required scope; 409 means the selected version is disabled; 422 means the model/client input violated its schema. Correlate a failure using the execution and correlation IDs without logging its content.

Live ServiceNow, Graph, Blob, and Key Vault calls are intentionally not part of CI. Verify each configured provider from the Integrations screen after deployment.
