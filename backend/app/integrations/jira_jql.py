from __future__ import annotations

import re
from dataclasses import dataclass

from app.integrations.errors import IntegrationError

_PROJECT_CLAUSE = re.compile(
    r"\bproject\s*=\s*(?:\"(?P<quoted>[A-Z][A-Z0-9_]*)\"|(?P<plain>[A-Z][A-Z0-9_]*))\b",
    re.IGNORECASE,
)
_FIELD = re.compile(
    r"(?:^|\bAND\b|\bOR\b)\s*([A-Za-z][A-Za-z0-9_.]*)\s+", re.IGNORECASE
)
_UNSAFE = re.compile(
    r"(?:/\*|\*/|--|\b(?:WAS|CHANGED|DURING|AFTER|BEFORE)\b|"
    r"\b(?:issueFunction|membersOf|linkedIssues|portfolioChildIssuesOf)\s*\()",
    re.IGNORECASE,
)
_ALLOWED_FIELDS = frozenset(
    {
        "project",
        "issuetype",
        "status",
        "priority",
        "assignee",
        "reporter",
        "resolution",
        "created",
        "updated",
        "duedate",
        "fixversion",
        "component",
        "labels",
        "key",
        "parent",
        "sprint",
        "summary",
    }
)


@dataclass(frozen=True)
class SafeJql:
    query: str
    project_key: str
    max_results: int


def validate_scoped_jql(
    raw_jql: str, *, authorized_project_key: str | None, max_results: int = 50
) -> SafeJql:
    """Validate the deliberately small JQL subset exposed to AI tool execution.

    This is a policy boundary, not a complete Jira grammar. Constructs we cannot
    prove safe are rejected instead of being forwarded to Jira.
    """
    query = " ".join(str(raw_jql or "").strip().split())
    if not query or len(query) > 2_000:
        raise _unsafe("JQL must be present and no longer than 2,000 characters")
    if _UNSAFE.search(query) or query.count("(") != query.count(")"):
        raise _unsafe("JQL contains an unsupported or unsafe construct")

    projects = {
        (match.group("quoted") or match.group("plain") or "").upper()
        for match in _PROJECT_CLAUSE.finditer(query)
    }
    trusted_project = str(authorized_project_key or "").strip().upper()
    if len(projects) != 1:
        raise _unsafe("JQL must contain exactly one explicit project = KEY clause")
    project = next(iter(projects))
    if not trusted_project:
        raise _unsafe("An authorized Jira project scope is required for raw JQL")
    if project != trusted_project:
        raise IntegrationError(
            "INSUFFICIENT_EXTERNAL_PERMISSION",
            "JQL project scope is outside the authorized Jira project",
            403,
        )

    fields = {match.group(1).casefold() for match in _FIELD.finditer(query)}
    unsupported = sorted(fields - _ALLOWED_FIELDS)
    if unsupported:
        raise _unsafe(f"JQL field is not allowed: {unsupported[0]}")

    bounded_limit = max(1, min(int(max_results), 100))
    return SafeJql(query=query, project_key=project, max_results=bounded_limit)


def _unsafe(message: str) -> IntegrationError:
    return IntegrationError("JIRA_JQL_UNSAFE", message, 422)
