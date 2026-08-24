from __future__ import annotations

from typing import ClassVar

from app.contracts.tool import Tool
from app.contracts.tool_models import ToolMetadata, ToolResult
from app.tool_sdk.adapters import (
    AzureBlobAdapter,
    AzureKeyVaultAdapter,
    LocalFileAdapter,
    ServiceNowAdapter,
)

OBJ = {"type": "object", "properties": {}, "additionalProperties": False}


def meta(
    name,
    display,
    description,
    category,
    provider,
    permission,
    properties,
    required=(),
    requirements=(),
):
    return ToolMetadata(
        name=name,
        display_name=display,
        description=description,
        category=category,
        provider=provider,
        version="1.0.0",
        permissions=(permission,),
        tags=(provider, "read"),
        parameters={
            "type": "object",
            "properties": properties,
            "required": list(required),
            "additionalProperties": False,
        },
        output_schema=None,
        risk_level="read",
        configuration_requirements=requirements,
    )


class ServiceNowSearchTool(Tool):
    tables: ClassVar[dict[str, str]] = {
        "servicenow_incident_search": "incident",
        "servicenow_change_search": "change_request",
        "servicenow_asset_search": "cmdb_ci",
    }
    fields: ClassVar[dict[str, str]] = {
        "incident": "sys_id,number,short_description,state,priority,assignment_group,assigned_to,sys_created_on,sys_updated_on",
        "change_request": "sys_id,number,short_description,state,risk,assignment_group,sys_created_on,sys_updated_on",
        "cmdb_ci": "sys_id,name,asset_tag,serial_number,install_status,sys_class_name,sys_updated_on",
    }

    def __init__(self, name, display, permission, adapter=None):
        self.adapter = adapter or ServiceNowAdapter()
        self.metadata = meta(
            name,
            display,
            f"Search approved {display.lower()} records",
            "it_service_management",
            "servicenow",
            permission,
            {
                "query": {"type": "string", "maxLength": 1000},
                "state": {"type": "string", "maxLength": 80},
                "priority": {"type": "string", "maxLength": 20},
                "assignment_group": {"type": "string", "maxLength": 120},
                "updated_after": {"type": "string", "maxLength": 60},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 25,
                },
                "offset": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10000,
                    "default": 0,
                },
            },
            requirements=("servicenow",),
        )

    async def execute(self, input_data, context):
        table = self.tables[self.name]
        query = input_data.get("query", "")
        if any(x in query for x in ("javascript:", "^NQ", "sysparm_")):
            from app.tool_sdk.errors import UnsafeOperationError

            raise UnsafeOperationError(
                "ServiceNow query contains a disallowed expression"
            )
        filters = [query] if query else []
        for key, column in (
            ("state", "state"),
            ("priority", "priority"),
            ("assignment_group", "assignment_group"),
            ("updated_after", "sys_updated_on>="),
        ):
            if input_data.get(key):
                filters.append(
                    f"{column}{'=' if not column.endswith('>=') else ''}{input_data[key]}"
                )
        rows, request_id = await self.adapter.search(
            table,
            {
                "sysparm_query": "^".join(filters),
                "sysparm_fields": self.fields[table],
                "sysparm_limit": input_data["limit"],
                "sysparm_offset": input_data["offset"],
                "sysparm_display_value": "true",
            },
        )
        return ToolResult.succeeded(
            {"items": rows, "count": len(rows), "offset": input_data["offset"]},
            provider_request_id=request_id,
            pagination={"offset": input_data["offset"], "limit": input_data["limit"]},
        )

    async def health(self):
        return await self.adapter.verify()


class ServiceNowIncidentGet(Tool):
    def __init__(self, adapter=None):
        self.adapter = adapter or ServiceNowAdapter()
        self.metadata = meta(
            "servicenow_incident_get",
            "ServiceNow Incident Get",
            "Retrieve an incident by approved identifier",
            "it_service_management",
            "servicenow",
            "servicenow.incidents.read",
            {"identifier": {"type": "string", "minLength": 1, "maxLength": 80}},
            ("identifier",),
            ("servicenow",),
        )

    async def execute(self, input_data, context):
        value = input_data["identifier"]
        rows, request_id = await self.adapter.search(
            "incident",
            {
                "sysparm_query": f"number={value}"
                if value.upper().startswith("INC")
                else f"sys_id={value}",
                "sysparm_fields": ServiceNowSearchTool.fields["incident"],
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            },
        )
        return ToolResult.succeeded(
            {"incident": rows[0] if rows else None}, provider_request_id=request_id
        )

    async def health(self):
        return await self.adapter.verify()


class LocalFileTool(Tool):
    def __init__(self, operation, adapter=None):
        self.adapter = adapter or LocalFileAdapter()
        props = {"path": {"type": "string", "minLength": 1, "maxLength": 1000}}
        if operation == "list":
            props |= {
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 25,
                },
            }
        permission = {
            "list": "files.read",
            "metadata": "files.metadata.read",
            "read": "files.read",
        }[operation]
        self.operation = operation
        self.metadata = meta(
            f"file_{operation}",
            f"File {operation.title()}",
            f"Securely {operation} approved server-side files",
            "files",
            "local_files",
            permission,
            props,
            ("path",),
            ("local_files",),
        )

    async def execute(self, input_data, context):
        if self.operation == "list":
            data = {
                "items": self.adapter.list(
                    input_data["path"], input_data["offset"], input_data["limit"]
                )
            }
        elif self.operation == "metadata":
            data = self.adapter.metadata(input_data["path"])
        else:
            data = {
                "content": self.adapter.read(input_data["path"]),
                "path": input_data["path"],
            }
        return ToolResult.succeeded(data)

    async def health(self):
        return await self.adapter.verify()


class AzureBlobTool(Tool):
    def __init__(self, operation, adapter=None):
        self.adapter = adapter or AzureBlobAdapter()
        self.operation = operation
        props = {
            "container": {"type": "string", "minLength": 1, "maxLength": 63},
            "blob": {"type": "string", "maxLength": 1024},
            "prefix": {"type": "string", "maxLength": 1024},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
        }
        required = ("container",) if operation == "list" else ("container", "blob")
        self.metadata = meta(
            f"azure_blob_{operation}",
            f"Azure Blob {operation.title()}",
            f"{operation.title()} approved Azure Blob content",
            "cloud_storage",
            "azure_blob",
            f"azure.blob.{operation if operation == 'read' else 'read'}",
            props,
            required,
            ("azure_blob",),
        )

    async def execute(self, input_data, context):
        self.adapter.allowed_container(input_data["container"])
        if self.operation == "list":
            data, request_id = await self.adapter.request(
                "GET",
                f"/{input_data['container']}",
                params={
                    "restype": "container",
                    "comp": "list",
                    "prefix": input_data.get("prefix", ""),
                    "maxresults": input_data["limit"],
                },
            )
        elif self.operation == "metadata":
            data, request_id = await self.adapter.request(
                "HEAD", f"/{input_data['container']}/{input_data['blob']}"
            )
        else:
            data, request_id = await self.adapter.request(
                "GET", f"/{input_data['container']}/{input_data['blob']}"
            )
        return ToolResult.succeeded(data, provider_request_id=request_id)

    async def health(self):
        return await self.adapter.verify()


class KeyVaultMetadataTool(Tool):
    def __init__(self, adapter=None):
        self.adapter = adapter or AzureKeyVaultAdapter()
        self.metadata = meta(
            "azure_keyvault_secret_metadata",
            "Azure Key Vault Secret Metadata",
            "Retrieve secret metadata without secret values",
            "secrets",
            "azure_keyvault",
            "azure.keyvault.secrets.read",
            {"name": {"type": "string", "maxLength": 127}},
            requirements=("azure_keyvault",),
        )

    async def execute(self, input_data, context):
        data, request_id = await self.adapter.metadata(input_data.get("name"))
        return ToolResult.succeeded(data, provider_request_id=request_id)

    async def health(self):
        return await self.adapter.verify()


class DeploymentReportTool(Tool):
    """Deterministic Tool SDK implementation used by agent workflows."""

    metadata = ToolMetadata(
        name="deployment_report",
        display_name="Deployment Report",
        description="Generate a standardized deployment report from validated release data",
        category="operations",
        provider="native",
        version="1.0.0",
        permissions=("deployment.reports.create",),
        tags=("deployment", "report", "operations"),
        parameters={
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "release_version": {"type": "string", "minLength": 1, "maxLength": 80},
                "environment": {
                    "type": "string",
                    "enum": ["development", "staging", "production"],
                },
                "status": {
                    "type": "string",
                    "enum": ["succeeded", "partial", "failed"],
                },
                "build": {"type": "string", "maxLength": 120},
                "issues": {"type": "string", "maxLength": 2000},
                "rollback_plan": {"type": "string", "maxLength": 2000},
            },
            "required": ["project_name", "release_version", "environment", "status"],
            "additionalProperties": False,
        },
        risk_level="write",
    )

    async def execute(self, input_data, context):
        report = (
            f"# Deployment Report: {input_data['project_name']}\n\n"
            f"- Release: {input_data['release_version']}\n"
            f"- Environment: {input_data['environment']}\n"
            f"- Status: {input_data['status']}\n"
            f"- Build: {input_data.get('build') or 'Not supplied'}\n\n"
            f"## Issues\n{input_data.get('issues') or 'None reported'}\n\n"
            f"## Rollback plan\n{input_data.get('rollback_plan') or 'Use the approved release rollback procedure.'}"
        )
        return ToolResult.succeeded({"report": report})


def builtin_tools():
    return [
        DeploymentReportTool(),
        ServiceNowSearchTool(
            "servicenow_incident_search",
            "ServiceNow Incident Search",
            "servicenow.incidents.read",
        ),
        ServiceNowIncidentGet(),
        ServiceNowSearchTool(
            "servicenow_change_search",
            "ServiceNow Change Search",
            "servicenow.changes.read",
        ),
        ServiceNowSearchTool(
            "servicenow_asset_search",
            "ServiceNow Asset Search",
            "servicenow.assets.read",
        ),
        LocalFileTool("list"),
        LocalFileTool("metadata"),
        AzureBlobTool("list"),
        AzureBlobTool("metadata"),
        AzureBlobTool("read"),
        KeyVaultMetadataTool(),
    ]
