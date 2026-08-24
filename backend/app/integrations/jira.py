from __future__ import annotations

from typing import Any

import httpx

from app.integrations.base import CapabilityDefinition, EnterpriseConnector
from app.integrations.errors import IntegrationError

OBJECT = {"type": "object", "additionalProperties": True}


def schema(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


CAPABILITIES = [
    CapabilityDefinition(
        "jira.get_projects",
        "Get Projects",
        "List accessible Jira projects",
        "tool",
        schema({}),
        {"type": "array"},
    ),
    CapabilityDefinition(
        "jira.search_issues",
        "Search Issues",
        "Search Jira issues with JQL",
        "tool",
        schema(
            {
                "jql": {"type": "string"},
                "project_key": {"type": "string", "x-normalize": "uppercase"},
                "issue_type": {
                    "type": "string",
                    "description": "A concrete Jira issue type such as Task, Bug, or Story. Generic phrases such as Jira ticket do not specify this value.",
                },
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            }
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_issue",
        "Get Issue",
        "Retrieve a Jira issue",
        "tool",
        schema({"issue_key": {"type": "string"}}, ["issue_key"]),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_create_metadata",
        "Get Create Metadata",
        "Retrieve project issue types and fields",
        "tool",
        schema(
            {
                "project_key": {"type": "string", "x-normalize": "uppercase"},
                "issue_type_id": {"type": "string"},
                "issue_type": {"type": "string"},
            },
            ["project_key"],
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_transitions",
        "Get Transitions",
        "List valid issue transitions",
        "tool",
        schema({"issue_key": {"type": "string"}}, ["issue_key"]),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.create_issue",
        "Create Issue",
        "Create a Jira issue",
        "action",
        schema(
            {
                "project_key": {"type": "string", "x-normalize": "uppercase"},
                "issue_type": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string"},
                "assignee": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "issue_type_id": {"type": "string"},
                "jira_fields": {"type": "object", "additionalProperties": True},
            },
            ["project_key", "issue_type", "summary"],
        ),
        OBJECT,
        "medium",
        True,
    ),
    CapabilityDefinition(
        "jira.update_issue",
        "Update Issue",
        "Update Jira issue fields",
        "action",
        schema(
            {"issue_key": {"type": "string"}, "fields": {"type": "object"}},
            ["issue_key", "fields"],
        ),
        OBJECT,
        "medium",
        True,
    ),
    CapabilityDefinition(
        "jira.add_comment",
        "Add Comment",
        "Add a comment to a Jira issue",
        "action",
        schema(
            {"issue_key": {"type": "string"}, "comment": {"type": "string"}},
            ["issue_key", "comment"],
        ),
        OBJECT,
        "medium",
        True,
    ),
    CapabilityDefinition(
        "jira.assign_issue",
        "Assign Issue",
        "Assign a Jira issue",
        "action",
        schema(
            {
                "issue_key": {"type": "string"},
                "account_id": {"type": ["string", "null"]},
            },
            ["issue_key"],
        ),
        OBJECT,
        "medium",
        True,
    ),
    CapabilityDefinition(
        "jira.transition_issue",
        "Transition Issue",
        "Move a Jira issue through its workflow",
        "action",
        schema(
            {"issue_key": {"type": "string"}, "transition_id": {"type": "string"}},
            ["issue_key", "transition_id"],
        ),
        OBJECT,
        "high",
        True,
    ),
]


class JiraConnector(EnterpriseConnector):
    connector_type = "jira"

    def validate_configuration(self, connection, secret: dict) -> None:
        if not connection.base_url.startswith("https://"):
            raise IntegrationError(
                "INVALID_CONFIGURATION", "Jira site URL must use HTTPS", 422
            )
        if connection.auth_type == "api_token" and not (
            secret.get("email") and (secret.get("api_token") or secret.get("token"))
        ):
            raise IntegrationError(
                "INVALID_CONFIGURATION",
                "Jira API-token credentials require email and api_token",
                422,
            )
        if connection.auth_type == "oauth2" and not secret.get("access_token"):
            raise IntegrationError(
                "TOKEN_EXPIRED", "The Jira OAuth connection must be authorized", 401
            )

    def _client(self, connection, secret: dict) -> httpx.AsyncClient:
        self.validate_configuration(connection, secret)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth = None
        if connection.auth_type == "api_token":
            auth = (secret["email"], secret.get("api_token") or secret["token"])
        else:
            headers["Authorization"] = f"Bearer {secret['access_token']}"
        return httpx.AsyncClient(
            base_url=connection.base_url.rstrip("/"),
            headers=headers,
            auth=auth,
            timeout=20,
            follow_redirects=False,
        )

    async def _request(
        self, connection, secret: dict, method: str, path: str, **kwargs
    ) -> Any:
        try:
            async with self._client(connection, secret) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise IntegrationError(
                "INTEGRATION_UNAVAILABLE", "Jira is currently unavailable"
            ) from exc
        if response.status_code in {401, 403}:
            raise IntegrationError(
                "INTEGRATION_AUTH_FAILED"
                if response.status_code == 401
                else "INSUFFICIENT_EXTERNAL_PERMISSION",
                "Jira rejected the configured credentials or permissions",
                response.status_code,
            )
        if response.status_code == 429:
            raise IntegrationError("RATE_LIMITED", "Jira rate limit reached", 429)
        if response.status_code >= 400:
            raise IntegrationError(
                "EXTERNAL_VALIDATION_FAILED",
                f"Jira rejected the request (HTTP {response.status_code})",
                422,
            )
        return response.json() if response.content else {}

    async def test_connection(self, connection, secret: dict) -> dict:
        myself = await self._request(connection, secret, "GET", "/rest/api/3/myself")
        return {
            "healthy": True,
            "account": myself.get("displayName"),
            "account_id": myself.get("accountId"),
        }

    async def discover_capabilities(self, connection, secret: dict):
        projects = await self._request(
            connection,
            secret,
            "GET",
            "/rest/api/3/project/search",
            params={"maxResults": 100},
        )
        safe_projects = [
            {
                "id": p.get("id"),
                "key": p.get("key"),
                "name": p.get("name"),
                "project_type": p.get("projectTypeKey"),
                "enabled": True,
            }
            for p in projects.get("values", [])
        ]
        return CAPABILITIES, {
            "projects": safe_projects,
            "project_count": len(safe_projects),
        }

    async def execute_tool(
        self, connection, capability: str, arguments: dict, secret: dict
    ):
        search_jql = arguments.get("jql") or self._search_jql(arguments)
        routes = {
            "jira.get_projects": (
                "GET",
                "/rest/api/3/project/search",
                {"params": {"maxResults": 100}},
            ),
            "jira.search_issues": (
                "POST",
                "/rest/api/3/search/jql",
                {
                    "json": {
                        "jql": search_jql,
                        "maxResults": arguments.get("max_results", 50),
                        "fields": [
                            "summary",
                            "status",
                            "priority",
                            "assignee",
                            "issuetype",
                            "project",
                        ],
                    }
                },
            ),
            "jira.get_issue": (
                "GET",
                f"/rest/api/3/issue/{arguments.get('issue_key', '')}",
                {},
            ),
            "jira.get_transitions": (
                "GET",
                f"/rest/api/3/issue/{arguments.get('issue_key', '')}/transitions",
                {},
            ),
        }
        if capability == "jira.get_create_metadata":
            project_key = arguments["project_key"]
            issue_types = await self._request(
                connection,
                secret,
                "GET",
                f"/rest/api/3/issue/createmeta/{project_key}/issuetypes",
                params={"maxResults": 100},
            )
            choices = issue_types.get("issueTypes", [])
            requested_id = arguments.get("issue_type_id")
            requested_name = str(arguments.get("issue_type") or "").casefold()
            selected = next(
                (
                    item
                    for item in choices
                    if str(item.get("id")) == str(requested_id)
                    or requested_name
                    and str(item.get("name", "")).casefold() == requested_name
                ),
                None,
            )
            result = {
                "project_key": project_key,
                "issue_types": [
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "subtask": bool(item.get("subtask")),
                    }
                    for item in choices
                ],
                "fields": [],
            }
            if requested_id or requested_name:
                if selected is None:
                    raise IntegrationError(
                        "JIRA_ISSUE_TYPE_INVALID",
                        "The selected issue type is not available for this Jira project",
                        422,
                    )
                field_page = await self._request(
                    connection,
                    secret,
                    "GET",
                    f"/rest/api/3/issue/createmeta/{project_key}/issuetypes/{selected['id']}",
                    params={"maxResults": 200},
                )
                result["selected_issue_type"] = {
                    "id": selected.get("id"),
                    "name": selected.get("name"),
                }
                result["fields"] = field_page.get("fields", [])
            return result
        if capability not in routes:
            raise IntegrationError(
                "CAPABILITY_UNAVAILABLE", "Jira tool is not implemented", 422
            )
        method, path, kwargs = routes[capability]
        return await self._request(connection, secret, method, path, **kwargs)

    @staticmethod
    def _search_jql(arguments: dict[str, Any]) -> str:
        """Compile validated semantic search fields into deterministic Jira JQL."""
        clauses: list[str] = []
        fields = {
            "project_key": "project",
            "issue_type": "issuetype",
            "status": "status",
            "assignee": "assignee",
        }
        for parameter, field in fields.items():
            value = arguments.get(parameter)
            if value in (None, ""):
                continue
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            clauses.append(f'{field} = "{escaped}"')
        return " AND ".join(clauses) or "order by updated DESC"

    @staticmethod
    def _doc(text: str) -> dict:
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            ],
        }

    async def execute_action(
        self, connection, capability: str, arguments: dict, secret: dict
    ):
        key = arguments.get("issue_key", "")
        if capability == "jira.create_issue":
            fields = {
                "project": {"key": arguments["project_key"]},
                "issuetype": (
                    {"id": arguments["issue_type_id"]}
                    if arguments.get("issue_type_id")
                    else {"name": arguments["issue_type"]}
                ),
                "summary": arguments["summary"],
            }
            fields.update(arguments.get("jira_fields") or {})
            for field in ("priority", "assignee"):
                if arguments.get(field):
                    fields[field] = {
                        "name" if field == "priority" else "accountId": arguments[field]
                    }
            if arguments.get("description"):
                fields["description"] = self._doc(arguments["description"])
            if arguments.get("labels"):
                fields["labels"] = arguments["labels"]
            result = await self._request(
                connection, secret, "POST", "/rest/api/3/issue", json={"fields": fields}
            )
            result["browse_url"] = (
                f"{connection.base_url.rstrip('/')}/browse/{result.get('key')}"
            )
            return result
        if capability == "jira.update_issue":
            method, path, kwargs = (
                "PUT",
                f"/rest/api/3/issue/{key}",
                {"json": {"fields": arguments["fields"]}},
            )
        elif capability == "jira.add_comment":
            method, path, kwargs = (
                "POST",
                f"/rest/api/3/issue/{key}/comment",
                {"json": {"body": self._doc(arguments["comment"])}},
            )
        elif capability == "jira.assign_issue":
            method, path, kwargs = (
                "PUT",
                f"/rest/api/3/issue/{key}/assignee",
                {"json": {"accountId": arguments.get("account_id")}},
            )
        elif capability == "jira.transition_issue":
            method, path, kwargs = (
                "POST",
                f"/rest/api/3/issue/{key}/transitions",
                {"json": {"transition": {"id": arguments["transition_id"]}}},
            )
        else:
            raise IntegrationError(
                "CAPABILITY_UNAVAILABLE", "Jira action is not implemented", 422
            )
        return await self._request(connection, secret, method, path, **kwargs)
