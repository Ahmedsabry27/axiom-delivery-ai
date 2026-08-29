from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.errors import IntegrationError
from app.integrations.jira import JiraConnector


@pytest.mark.asyncio
async def test_search_issues_uses_bounded_all_history_default(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"issues": []})
    monkeypatch.setattr(connector, "_request", request)

    await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.search_issues",
        {},
        {},
    )

    assert request.await_args.args[2:4] == ("POST", "/rest/api/3/search/jql")
    assert request.await_args.kwargs["json"]["jql"] == (
        'created >= "1970-01-01" ORDER BY updated DESC'
    )


@pytest.mark.asyncio
async def test_search_issues_compiles_status_and_priority_filters(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"issues": []})
    monkeypatch.setattr(connector, "_request", request)

    await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.search_issues",
        {"status": "In Progress", "priority": "High"},
        {},
    )

    assert request.await_args.kwargs["json"]["jql"] == (
        'status = "In Progress" AND priority = "High"'
    )


@pytest.mark.asyncio
async def test_search_issues_validates_raw_jql_against_trusted_project(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"issues": []})
    monkeypatch.setattr(connector, "_request", request)

    await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.search_issues",
        {
            "jql": "project = SOAI AND status = Open",
            "project_key": "SOAI",
            "max_results": 250,
        },
        {},
    )

    payload = request.await_args.kwargs["json"]
    assert payload["jql"] == "project = SOAI AND status = Open"
    assert payload["maxResults"] == 100


@pytest.mark.asyncio
async def test_get_issue_adds_trusted_browse_url(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"key": "AIGOV-6", "fields": {}})
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_issue",
        {"issue_key": "AIGOV-6"},
        {},
    )

    assert result["browse_url"] == "https://jira.example/browse/AIGOV-6"
    assert result["evidence"]["source"] == "jira_live_api"
    assert result["evidence"]["source_url"] == result["browse_url"]
    assert result["evidence"]["freshness"] == "live"


@pytest.mark.asyncio
async def test_get_comments_uses_comments_endpoint_and_adds_evidence(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"comments": [{"id": "1", "body": {}}]})
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_comments",
        {"issue_key": "AIDP-1", "max_results": 200},
        {},
    )

    assert request.await_args.args[2:4] == (
        "GET",
        "/rest/api/3/issue/AIDP-1/comment",
    )
    assert request.await_args.kwargs["params"]["maxResults"] == 100
    assert result["issue_key"] == "AIDP-1"
    assert result["evidence"]["freshness"] == "live"


@pytest.mark.asyncio
async def test_get_sprint_health_calculates_requested_dimensions(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(
        side_effect=[
            {"values": [{"id": 7, "name": "AI Board"}]},
            {"values": [{"id": 22, "name": "Sprint 2 – AI Insights Delivery"}]},
            {
                "isLast": True,
                "issues": [
                    {
                        "key": "AIDP-1",
                        "fields": {
                            "summary": "Blocked foundation",
                            "status": {
                                "name": "Blocked",
                                "statusCategory": {"key": "indeterminate"},
                            },
                            "labels": ["blocked"],
                            "duedate": "2020-01-01",
                            "issuetype": {"name": "Story"},
                            "issuelinks": [{"id": "1"}],
                        },
                    },
                    {
                        "key": "AIDP-2",
                        "fields": {
                            "summary": "Completed defect",
                            "status": {
                                "name": "Done",
                                "statusCategory": {"key": "done"},
                            },
                            "labels": [],
                            "issuetype": {"name": "Bug"},
                            "issuelinks": [],
                        },
                    },
                ],
            },
        ]
    )
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_sprint_health",
        {"sprint_name": "Sprint 2 – AI Insights Delivery"},
        {},
    )

    assert result["health"] == "AT_RISK"
    assert result["confidence"] == "MEDIUM"
    assert result["metrics"] == {
        "issues": 2,
        "completed": 1,
        "completion_rate": 50.0,
        "blockers": 1,
        "dependencies": 1,
        "overdue": 1,
        "defects": 1,
        "known_risk_items": 2,
    }
    assert len(result["recommended_actions"]) == 5
    assert result["evidence"]["partial"] is False


@pytest.mark.asyncio
async def test_get_sprint_health_not_found_suggests_accessible_names(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(
        side_effect=[
            {"values": [{"id": 7, "name": "AI Board"}]},
            {
                "values": [
                    {"id": 22, "name": "AIGOV S2 Integrated"},
                    {"id": 23, "name": "OPSINT S2 Integrated"},
                ]
            },
        ]
    )
    monkeypatch.setattr(connector, "_request", request)

    with pytest.raises(IntegrationError) as error:
        await connector.execute_tool(
            SimpleNamespace(base_url="https://jira.example"),
            "jira.get_sprint_health",
            {"sprint_name": "Sprint 2 – AI Insights Delivery"},
            {},
        )

    assert error.value.code == "JIRA_SPRINT_NOT_FOUND"
    assert "AIGOV S2 Integrated" in error.value.safe_message
    assert "Use an exact Jira sprint name" in error.value.safe_message


@pytest.mark.asyncio
async def test_get_sprints_lists_active_sprints_and_deduplicates_shared_sprint(monkeypatch):
    connector = JiraConnector()
    sprint = {
        "id": 22,
        "name": "Sprint 2",
        "state": "active",
        "goal": "Deliver insights",
    }
    request = AsyncMock(
        side_effect=[
            {
                "values": [
                    {"id": 7, "name": "Board A"},
                    {"id": 8, "name": "Board B"},
                ]
            },
            {"values": [sprint]},
            {"values": [sprint]},
        ]
    )
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_sprints",
        {"state": "active"},
        {},
    )

    assert result["count"] == 1
    assert result["sprints"][0]["name"] == "Sprint 2"
    assert result["state"] == "active"
    assert result["evidence"]["freshness"] == "live"


@pytest.mark.asyncio
async def test_empty_sprint_health_is_unknown_not_healthy(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(
        side_effect=[
            {"values": [{"id": 7, "name": "OPSINT Board"}]},
            {"values": [{"id": 22, "name": "OPSINT S2 Integrated"}]},
            {"isLast": True, "issues": []},
        ]
    )
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_sprint_health",
        {"sprint_name": "OPSINT S2 Integrated"},
        {},
    )

    assert result["health"] == "UNKNOWN"
    assert result["confidence"] == "LOW"
    assert result["metrics"]["completion_rate"] is None


@pytest.mark.asyncio
async def test_search_issues_adds_trusted_links_and_query_evidence(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(return_value={"issues": [{"key": "SOAI-7"}]})
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.search_issues",
        {"project_key": "SOAI", "status": "In Progress"},
        {},
    )

    assert result["issues"][0]["browse_url"] == "https://jira.example/browse/SOAI-7"
    assert result["evidence"]["executed_jql"] == (
        'project = "SOAI" AND status = "In Progress"'
    )
    assert result["evidence"]["freshness"] == "live"


@pytest.mark.asyncio
async def test_get_versions_returns_only_planned_releases_across_projects(monkeypatch):
    connector = JiraConnector()
    request = AsyncMock(
        side_effect=[
            {"values": [{"key": "SOAI", "name": "Service Operations AI"}]},
            [
                {
                    "id": "10",
                    "name": "SOAI 1.0",
                    "released": False,
                    "archived": False,
                    "releaseDate": "2026-09-30",
                },
                {"id": "9", "name": "Old", "released": True, "archived": False},
                {"id": "8", "name": "Archived", "released": False, "archived": True},
            ],
        ]
    )
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_versions",
        {},
        {},
    )

    assert result["count"] == 1
    assert result["releases"][0] == {
        "id": "10",
        "name": "SOAI 1.0",
        "description": None,
        "project_key": "SOAI",
        "project_name": "Service Operations AI",
        "status": "planned",
        "start_date": None,
        "release_date": "2026-09-30",
        "overdue": False,
        "browse_url": (
            "https://jira.example/plugins/servlet/project-config/SOAI/versions/10"
        ),
    }
    assert result["evidence"]["freshness"] == "live"


@pytest.mark.asyncio
async def test_get_version_issues_resolves_version_id_then_searches_fix_version(monkeypatch):
    connector = JiraConnector()
    monkeypatch.setattr(
        connector,
        "_get_versions",
        AsyncMock(
            return_value={
                "releases": [
                    {
                        "id": "10004",
                        "name": "Phase 5 — Portfolio Intelligence",
                        "project_key": "AIDP",
                        "browse_url": "https://jira.example/releases/10004",
                    }
                ]
            }
        ),
    )
    request = AsyncMock(
        return_value={
            "issues": [{"key": "AIDP-50", "fields": {"summary": "Portfolio"}}]
        }
    )
    monkeypatch.setattr(connector, "_request", request)

    result = await connector.execute_tool(
        SimpleNamespace(base_url="https://jira.example"),
        "jira.get_version_issues",
        {"release_name": "Phase 5 — Portfolio Intelligence"},
        {},
    )

    assert request.await_args.kwargs["json"]["jql"] == (
        "fixVersion = 10004 ORDER BY key ASC"
    )
    assert result["release"]["project_key"] == "AIDP"
    assert result["issues"][0]["browse_url"] == "https://jira.example/browse/AIDP-50"


@pytest.mark.asyncio
async def test_get_version_issues_fails_closed_on_ambiguous_release(monkeypatch):
    connector = JiraConnector()
    monkeypatch.setattr(
        connector,
        "_get_versions",
        AsyncMock(
            return_value={
                "releases": [
                    {"id": "1", "name": "Release 1", "project_key": "ONE"},
                    {"id": "2", "name": "Release 1", "project_key": "TWO"},
                ]
            }
        ),
    )

    with pytest.raises(IntegrationError) as error:
        await connector.execute_tool(
            SimpleNamespace(base_url="https://jira.example"),
            "jira.get_version_issues",
            {"release_name": "Release 1"},
            {},
        )

    assert error.value.code == "JIRA_RELEASE_AMBIGUOUS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "arguments", "method", "path"),
    [
        (
            "jira.update_issue",
            {"issue_key": "OPS-1", "fields": {"summary": "Updated"}},
            "PUT",
            "/rest/api/3/issue/OPS-1",
        ),
        (
            "jira.add_comment",
            {"issue_key": "OPS-1", "comment": "Verified"},
            "POST",
            "/rest/api/3/issue/OPS-1/comment",
        ),
        (
            "jira.assign_issue",
            {"issue_key": "OPS-1", "account_id": "account-1"},
            "PUT",
            "/rest/api/3/issue/OPS-1/assignee",
        ),
        (
            "jira.transition_issue",
            {"issue_key": "OPS-1", "transition_id": "31"},
            "POST",
            "/rest/api/3/issue/OPS-1/transitions",
        ),
    ],
)
async def test_action_dispatch_evaluates_only_selected_capability(
    monkeypatch, capability, arguments, method, path
):
    connector = JiraConnector()
    request = AsyncMock(return_value={})
    monkeypatch.setattr(connector, "_request", request)

    await connector.execute_action(object(), capability, arguments, {})

    assert request.await_args.args[2:4] == (method, path)
