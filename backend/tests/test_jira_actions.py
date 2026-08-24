from unittest.mock import AsyncMock

import pytest

from app.integrations.jira import JiraConnector


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
