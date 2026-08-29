from __future__ import annotations

import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.integrations.base import CapabilityDefinition, EnterpriseConnector
from app.integrations.errors import IntegrationError
from app.integrations.jira_jql import validate_scoped_jql

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
        {
            "type": "object",
            "properties": {
                "values": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                }
            },
            "required": ["values"],
            "additionalProperties": True,
        },
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
                "priority": {"type": "string"},
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
        "jira.get_comments",
        "Get Issue Comments",
        "Retrieve comments from one Jira issue",
        "tool",
        schema(
            {
                "issue_key": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["issue_key"],
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_sprint_health",
        "Assess Sprint Health",
        "Resolve a Jira sprint and assess performance, blockers, dependencies, overdue work, and defects",
        "tool",
        schema(
            {
                "sprint_name": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["sprint_name"],
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_sprints",
        "List Jira Sprints",
        "List accessible Jira sprints filtered by lifecycle state",
        "tool",
        schema(
            {
                "state": {
                    "type": "string",
                    "enum": ["active", "future", "closed"],
                },
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            }
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_versions",
        "Get Planned Releases",
        "List planned Jira project versions, optionally within one project",
        "tool",
        schema(
            {
                "project_key": {"type": "string", "x-normalize": "uppercase"},
                "include_released": {"type": "boolean"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            }
        ),
        OBJECT,
    ),
    CapabilityDefinition(
        "jira.get_version_issues",
        "Get Release Tickets",
        "Resolve a Jira version and list the issues assigned to that release",
        "tool",
        schema(
            {
                "release_name": {"type": "string"},
                "project_key": {"type": "string", "x-normalize": "uppercase"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["release_name"],
        ),
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
        search_jql = self._search_jql(arguments)
        search_limit = max(1, min(int(arguments.get("max_results", 50)), 100))
        if arguments.get("jql"):
            safe_jql = validate_scoped_jql(
                arguments["jql"],
                authorized_project_key=arguments.get("project_key"),
                max_results=search_limit,
            )
            search_jql = safe_jql.query
            search_limit = safe_jql.max_results
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
                        "maxResults": search_limit,
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
            "jira.get_comments": (
                "GET",
                f"/rest/api/3/issue/{arguments.get('issue_key', '')}/comment",
                {
                    "params": {
                        "maxResults": max(
                            1, min(int(arguments.get("max_results", 50)), 100)
                        ),
                        "orderBy": "created",
                    }
                },
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
        if capability == "jira.get_versions":
            return await self._get_versions(connection, secret, arguments)
        if capability == "jira.get_version_issues":
            return await self._get_version_issues(connection, secret, arguments)
        if capability == "jira.get_sprint_health":
            return await self._get_sprint_health(connection, secret, arguments)
        if capability == "jira.get_sprints":
            return await self._get_sprints(connection, secret, arguments)
        if capability not in routes:
            raise IntegrationError(
                "CAPABILITY_UNAVAILABLE", "Jira tool is not implemented", 422
            )
        method, path, kwargs = routes[capability]
        result = await self._request(connection, secret, method, path, **kwargs)
        retrieved_at = datetime.now(UTC).isoformat()
        if capability == "jira.search_issues":
            base_url = connection.base_url.rstrip("/")
            for issue in result.get("issues", []):
                issue_key = issue.get("key")
                if issue_key:
                    issue["browse_url"] = f"{base_url}/browse/{issue_key}"
            result["evidence"] = {
                "source": "jira_live_api",
                "source_url": base_url,
                "retrieved_at": retrieved_at,
                "freshness": "live",
                "executed_jql": search_jql,
                "result_limit": search_limit,
            }
        if capability == "jira.get_issue":
            issue_key = result.get("key") or arguments.get("issue_key", "")
            result["browse_url"] = (
                f"{connection.base_url.rstrip('/')}/browse/{issue_key}"
            )
            result["evidence"] = {
                "source": "jira_live_api",
                "source_url": result["browse_url"],
                "retrieved_at": retrieved_at,
                "freshness": "live",
                "issue_key": issue_key,
            }
        if capability == "jira.get_comments":
            issue_key = str(arguments.get("issue_key") or "").upper()
            result["issue_key"] = issue_key
            result["browse_url"] = (
                f"{connection.base_url.rstrip('/')}/browse/{issue_key}"
            )
            result["evidence"] = {
                "source": "jira_live_api",
                "source_url": result["browse_url"],
                "retrieved_at": retrieved_at,
                "freshness": "live",
                "issue_key": issue_key,
                "result_limit": max(
                    1, min(int(arguments.get("max_results", 50)), 100)
                ),
            }
        return result

    async def _get_versions(
        self, connection, secret: dict, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        requested_project = str(arguments.get("project_key") or "").strip().upper()
        limit = max(1, min(int(arguments.get("max_results", 50)), 100))
        if requested_project:
            projects = [{"key": requested_project, "name": requested_project}]
        else:
            project_page = await self._request(
                connection,
                secret,
                "GET",
                "/rest/api/3/project/search",
                params={"maxResults": 100},
            )
            projects = project_page.get("values") or []

        releases: list[dict[str, Any]] = []
        base_url = connection.base_url.rstrip("/")
        for project in projects:
            project_key = str(project.get("key") or "").upper()
            if not project_key or len(releases) >= limit:
                continue
            versions = await self._request(
                connection,
                secret,
                "GET",
                f"/rest/api/3/project/{project_key}/versions",
            )
            for version in versions if isinstance(versions, list) else []:
                released = bool(version.get("released"))
                archived = bool(version.get("archived"))
                if archived or (released and not arguments.get("include_released", False)):
                    continue
                version_id = version.get("id")
                releases.append(
                    {
                        "id": version_id,
                        "name": version.get("name") or "Unnamed release",
                        "description": version.get("description"),
                        "project_key": project_key,
                        "project_name": project.get("name") or project_key,
                        "status": "released" if released else "planned",
                        "start_date": version.get("startDate"),
                        "release_date": version.get("releaseDate"),
                        "overdue": bool(version.get("overdue")),
                        "browse_url": (
                            f"{base_url}/plugins/servlet/project-config/"
                            f"{project_key}/versions/{version_id}"
                            if version_id
                            else None
                        ),
                    }
                )
                if len(releases) >= limit:
                    break

        releases.sort(
            key=lambda item: (
                item.get("release_date") is None,
                item.get("release_date") or "9999-12-31",
                item["project_key"],
                item["name"],
            )
        )
        return {
            "releases": releases,
            "count": len(releases),
            "evidence": {
                "source": "jira_live_api",
                "source_url": base_url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "freshness": "live",
                "project_scope": requested_project or "accessible_projects",
                "result_limit": limit,
            },
        }

    async def _get_version_issues(
        self, connection, secret: dict, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        release_name = str(arguments.get("release_name") or "").strip()
        if not release_name:
            raise IntegrationError(
                "JIRA_RELEASE_REQUIRED", "A Jira release name is required", 422
            )
        version_result = await self._get_versions(
            connection,
            secret,
            {
                "project_key": arguments.get("project_key"),
                "include_released": True,
                "max_results": 100,
            },
        )
        matches = [
            item
            for item in version_result["releases"]
            if str(item.get("name") or "").casefold() == release_name.casefold()
        ]
        if not matches:
            raise IntegrationError(
                "JIRA_RELEASE_NOT_FOUND",
                "No accessible Jira release matched that name",
                404,
            )
        if len(matches) > 1:
            raise IntegrationError(
                "JIRA_RELEASE_AMBIGUOUS",
                "That release name exists in more than one accessible Jira project",
                422,
            )
        release = matches[0]
        limit = max(1, min(int(arguments.get("max_results", 50)), 100))
        result = await self._request(
            connection,
            secret,
            "POST",
            "/rest/api/3/search/jql",
            json={
                "jql": f'fixVersion = {release["id"]} ORDER BY key ASC',
                "maxResults": limit,
                "fields": [
                    "summary",
                    "status",
                    "priority",
                    "assignee",
                    "issuetype",
                    "project",
                ],
            },
        )
        base_url = connection.base_url.rstrip("/")
        for issue in result.get("issues", []):
            if issue.get("key"):
                issue["browse_url"] = f"{base_url}/browse/{issue['key']}"
        result["release"] = release
        result["evidence"] = {
            "source": "jira_live_api",
            "source_url": release.get("browse_url") or base_url,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "freshness": "live",
            "version_id": release["id"],
            "project_key": release["project_key"],
            "result_limit": limit,
        }
        return result

    async def _get_sprint_health(
        self, connection, secret: dict, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        sprint_name = str(arguments.get("sprint_name") or "").strip()
        if not sprint_name:
            raise IntegrationError(
                "JIRA_SPRINT_REQUIRED", "A Jira sprint name is required", 422
            )
        boards = await self._request(
            connection,
            secret,
            "GET",
            "/rest/agile/1.0/board",
            params={"maxResults": 100},
        )
        normalized_name = re.sub(r"\s+", " ", re.sub(r"[‐‑‒–—−]", "-", sprint_name)).casefold()
        matches: dict[str, dict[str, Any]] = {}
        accessible_sprints: dict[str, dict[str, Any]] = {}
        for board in boards.get("values") or []:
            board_id = board.get("id")
            if board_id is None:
                continue
            try:
                sprint_page = await self._request(
                    connection,
                    secret,
                    "GET",
                    f"/rest/agile/1.0/board/{board_id}/sprint",
                    params={"maxResults": 100},
                )
            except IntegrationError as exc:
                if exc.code == "EXTERNAL_VALIDATION_FAILED":
                    # Jira returns 400 for Kanban and other boards without sprints.
                    continue
                raise
            for sprint in sprint_page.get("values") or []:
                sprint_id = str(sprint.get("id") or "")
                if sprint_id:
                    accessible_sprints[sprint_id] = sprint
                candidate_name = re.sub(
                    r"\s+",
                    " ",
                    re.sub(r"[‐‑‒–—−]", "-", str(sprint.get("name") or "")),
                ).casefold()
                if candidate_name == normalized_name:
                    matches[sprint_id] = sprint
        if not matches:
            ranked = sorted(
                accessible_sprints.values(),
                key=lambda item: SequenceMatcher(
                    None,
                    normalized_name,
                    re.sub(
                        r"\s+",
                        " ",
                        re.sub(r"[‐‑‒–—−]", "-", str(item.get("name") or "")),
                    ).casefold(),
                ).ratio(),
                reverse=True,
            )
            suggestions = [str(item.get("name")) for item in ranked[:5] if item.get("name")]
            suffix = (
                f" Closest accessible sprint names: {', '.join(suggestions)}."
                if suggestions
                else ""
            )
            raise IntegrationError(
                "JIRA_SPRINT_NOT_FOUND",
                "No accessible Jira sprint matched that name."
                f"{suffix} Use an exact Jira sprint name.",
                404,
            )
        if len(matches) > 1:
            raise IntegrationError(
                "JIRA_SPRINT_AMBIGUOUS",
                "That sprint name matches more than one accessible Jira sprint",
                422,
            )
        sprint = next(iter(matches.values()))
        sprint_id = sprint["id"]
        limit = max(1, min(int(arguments.get("max_results", 100)), 100))
        issue_page = await self._request(
            connection,
            secret,
            "GET",
            f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            params={
                "maxResults": limit,
                "fields": (
                    "summary,status,issuetype,priority,assignee,duedate,labels,"
                    "issuelinks,created,resolutiondate,project"
                ),
            },
        )
        issues = issue_page.get("issues") or []
        base_url = connection.base_url.rstrip("/")
        today = datetime.now(UTC).date().isoformat()
        completed: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        dependencies: list[dict[str, Any]] = []
        overdue: list[dict[str, Any]] = []
        defects: list[dict[str, Any]] = []
        for issue in issues:
            fields = issue.get("fields") or {}
            key = issue.get("key") or "—"
            item = {
                "key": key,
                "summary": fields.get("summary") or "Untitled",
                "status": (fields.get("status") or {}).get("name") or "Unknown",
                "browse_url": f"{base_url}/browse/{key}",
            }
            done = (fields.get("status") or {}).get("statusCategory", {}).get("key") == "done"
            labels = {str(value).casefold() for value in fields.get("labels") or []}
            status = item["status"].casefold()
            if done:
                completed.append(item)
            if not done and ("blocked" in labels or status in {"blocked", "impeded"}):
                blockers.append(item)
            links = fields.get("issuelinks") or []
            if links:
                dependencies.append({**item, "link_count": len(links)})
            due_date = fields.get("duedate")
            if not done and due_date and str(due_date) < today:
                overdue.append({**item, "due_date": due_date})
            if str((fields.get("issuetype") or {}).get("name") or "").casefold() in {
                "bug",
                "defect",
            }:
                defects.append({**item, "created": fields.get("created")})

        total = len(issues)
        completion_rate = round(len(completed) / total * 100, 1) if total else None
        missing = [
            "Original committed sprint scope and scope-change history are unavailable without sprint changelog snapshots.",
            "Story-point commitment and velocity are unavailable because no trusted story-point field mapping is configured.",
            "Defect trend direction requires comparable prior-sprint snapshots; this response reports the current sprint defect count only.",
            "Cross-team dependencies without Jira issue links cannot be detected.",
        ]
        risk_count = len(blockers) + len(overdue)
        health = (
            "UNKNOWN"
            if not total
            else "AT_RISK"
            if blockers or overdue or (completion_rate is not None and completion_rate < 70)
            else "HEALTHY"
        )
        confidence = "MEDIUM" if total else "LOW"
        actions = [
            "Assign an owner and resolution date to every blocked or impeded ticket.",
            "Review overdue open tickets and either complete, descoped, or re-plan them explicitly.",
            "Validate every linked dependency with its owning team and record the needed-by date.",
            "Triage sprint defects by severity and protect capacity for the highest-impact fixes.",
            "Configure story-point mapping and sprint scope snapshots before the next sprint review.",
        ]
        return {
            "sprint": sprint,
            "health": health,
            "confidence": confidence,
            "metrics": {
                "issues": total,
                "completed": len(completed),
                "completion_rate": completion_rate,
                "blockers": len(blockers),
                "dependencies": len(dependencies),
                "overdue": len(overdue),
                "defects": len(defects),
                "known_risk_items": risk_count,
            },
            "blockers": blockers,
            "dependencies": dependencies,
            "overdue": overdue,
            "defects": defects,
            "missing_information": missing,
            "recommended_actions": actions,
            "evidence": {
                "source": "jira_live_api",
                "source_url": f"{base_url}/jira/software/c/projects/board",
                "retrieved_at": datetime.now(UTC).isoformat(),
                "freshness": "live",
                "sprint_id": sprint_id,
                "issue_count": total,
                "result_limit": limit,
                "partial": bool(issue_page.get("isLast") is False or total >= limit),
            },
        }

    async def _get_sprints(
        self, connection, secret: dict, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        state = str(arguments.get("state") or "active").casefold()
        if state not in {"active", "future", "closed"}:
            raise IntegrationError(
                "JIRA_SPRINT_STATE_INVALID", "Unsupported Jira sprint state", 422
            )
        limit = max(1, min(int(arguments.get("max_results", 100)), 100))
        boards = await self._request(
            connection,
            secret,
            "GET",
            "/rest/agile/1.0/board",
            params={"maxResults": 100},
        )
        sprints: dict[str, dict[str, Any]] = {}
        for board in boards.get("values") or []:
            board_id = board.get("id")
            if board_id is None or len(sprints) >= limit:
                continue
            try:
                page = await self._request(
                    connection,
                    secret,
                    "GET",
                    f"/rest/agile/1.0/board/{board_id}/sprint",
                    params={"maxResults": 100, "state": state},
                )
            except IntegrationError as exc:
                if exc.code == "EXTERNAL_VALIDATION_FAILED":
                    continue
                raise
            for sprint in page.get("values") or []:
                sprint_id = str(sprint.get("id") or "")
                if sprint_id:
                    sprints[sprint_id] = {
                        "id": sprint.get("id"),
                        "name": sprint.get("name") or "Unnamed sprint",
                        "state": sprint.get("state") or state,
                        "goal": sprint.get("goal"),
                        "start_date": sprint.get("startDate"),
                        "end_date": sprint.get("endDate"),
                        "board_id": board_id,
                        "board_name": board.get("name") or "Unnamed board",
                    }
                if len(sprints) >= limit:
                    break
        values = sorted(
            sprints.values(), key=lambda item: (item["name"].casefold(), item["id"])
        )
        return {
            "sprints": values,
            "count": len(values),
            "state": state,
            "evidence": {
                "source": "jira_live_api",
                "source_url": connection.base_url.rstrip("/"),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "freshness": "live",
                "result_limit": limit,
            },
        }

    @staticmethod
    def _search_jql(arguments: dict[str, Any]) -> str:
        """Compile validated semantic search fields into deterministic Jira JQL."""
        clauses: list[str] = []
        fields = {
            "project_key": "project",
            "issue_type": "issuetype",
            "status": "status",
            "priority": "priority",
            "assignee": "assignee",
        }
        for parameter, field in fields.items():
            value = arguments.get(parameter)
            if value in (None, ""):
                continue
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            clauses.append(f'{field} = "{escaped}"')
        # Jira's enhanced search endpoint rejects a bare ORDER BY as an
        # unbounded query. The lower date bound preserves an all-history
        # default while satisfying Jira's required search restriction.
        return " AND ".join(clauses) or 'created >= "1970-01-01" ORDER BY updated DESC'

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
