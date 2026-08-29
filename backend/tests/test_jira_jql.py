import pytest

from app.integrations.errors import IntegrationError
from app.integrations.jira_jql import validate_scoped_jql


def test_accepts_a_bounded_allowlisted_single_project_query():
    result = validate_scoped_jql(
        'project = SOAI AND issuetype = Story AND status = "In Progress" '
        "AND priority = High ORDER BY updated DESC",
        authorized_project_key="soai",
        max_results=500,
    )

    assert result.project_key == "SOAI"
    assert result.max_results == 100


@pytest.mark.parametrize(
    "query",
    [
        "status = Open",
        "project = SOAI OR project = OPS",
        'project = SOAI AND issueFunction in linkedIssues("SOAI-1")',
        "project = SOAI AND secretField = hidden",
        "project = SOAI /* ignore policy */",
    ],
)
def test_rejects_unscoped_or_unsupported_jql(query):
    with pytest.raises(IntegrationError) as error:
        validate_scoped_jql(query, authorized_project_key="SOAI")

    assert error.value.code == "JIRA_JQL_UNSAFE"


def test_rejects_a_project_outside_the_trusted_scope():
    with pytest.raises(IntegrationError) as error:
        validate_scoped_jql(
            "project = FIN AND status = Open", authorized_project_key="SOAI"
        )

    assert error.value.code == "INSUFFICIENT_EXTERNAL_PERMISSION"
