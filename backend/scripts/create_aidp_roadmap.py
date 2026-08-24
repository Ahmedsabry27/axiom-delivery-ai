"""Create the approved AIDP roadmap, epics, and linked stories in real Jira."""

from __future__ import annotations

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

PROJECT = "AIDP"
ROADMAP = [
    {
        "version": "Phase 1 — Platform Foundation",
        "start": "2026-08-24",
        "release": "2026-09-30",
        "epic": "Establish enterprise platform foundation",
        "goal": "Provide secure identity, tenancy, navigation, runtime, and reliable delivery-data foundations.",
        "stories": [
            "As a platform administrator, I can manage tenant-aware users and roles",
            "As a delivery leader, I can navigate a consistent enterprise workspace",
            "As an operator, I can monitor frontend, backend, and database health",
            "As a product team, I can use seeded delivery data when a provider is unavailable",
        ],
    },
    {
        "version": "Phase 2 — Enterprise Integrations",
        "start": "2026-10-01",
        "release": "2026-10-31",
        "epic": "Connect trusted enterprise delivery systems",
        "goal": "Synchronize governed, traceable information from Jira, Confluence, Outlook, and Teams.",
        "stories": [
            "As a delivery manager, I can synchronize Jira projects, boards, and issues",
            "As a knowledge owner, I can synchronize Confluence spaces and pages",
            "As a meeting owner, I can synchronize Outlook calendars and events",
            "As a collaboration lead, I can view calendar-backed Microsoft Teams meetings",
        ],
    },
    {
        "version": "Phase 3 — Agentic Orchestration",
        "start": "2026-11-01",
        "release": "2026-11-30",
        "epic": "Deliver governed agents and workflow orchestration",
        "goal": "Enable reusable agents, workflows, tools, and human-controlled execution paths.",
        "stories": [
            "As an agent builder, I can configure and test an enterprise AI agent",
            "As a workflow designer, I can compose multi-step governed automations",
            "As a tool administrator, I can discover and approve runtime capabilities",
            "As an operator, I can inspect execution traces and recover failed runs",
        ],
    },
    {
        "version": "Phase 4 — Governance and Release Control",
        "start": "2026-12-01",
        "release": "2026-12-31",
        "epic": "Operationalize governance and release readiness",
        "goal": "Make approvals, risks, dependencies, evidence, and release decisions auditable.",
        "stories": [
            "As an approver, I can review structured actions in a consistent table",
            "As a release manager, I can assess readiness using evidence-backed controls",
            "As a programme lead, I can manage risks, assumptions, issues, and dependencies",
            "As an auditor, I can trace decisions, approvals, and integration activity",
        ],
    },
    {
        "version": "Phase 5 — Portfolio Intelligence",
        "start": "2027-01-01",
        "release": "2027-01-31",
        "epic": "Scale portfolio intelligence and executive insights",
        "goal": "Turn governed delivery data into prioritised, explainable portfolio decisions.",
        "stories": [
            "As an executive, I can view portfolio health, trends, and critical exceptions",
            "As a delivery leader, I can receive a populated daily briefing and action plan",
            "As a portfolio analyst, I can compare delivery health across projects and releases",
            "As a decision maker, I can inspect evidence behind AI-generated recommendations",
        ],
    },
]


def adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def require(response: httpx.Response, operation: str) -> dict:
    if response.status_code not in {200, 201}:
        try:
            body = response.json()
            errors = body.get("errorMessages") or list((body.get("errors") or {}).values())
        except ValueError:
            errors = []
        raise SystemExit(f"{operation} failed ({response.status_code}): {'; '.join(map(str, errors)) or 'Provider rejected the request'}")
    return response.json()


def main() -> None:
    db = SessionLocal()
    try:
        connection = db.query(IntegrationConnection).filter_by(
            tenant_id="axiom-demo", connector_type="jira"
        ).one()
        credential = secret_provider.resolve(connection.secret_ref)
        with httpx.Client(
            base_url=connection.base_url,
            auth=(credential["email"], credential["api_token"]),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
            follow_redirects=False,
        ) as client:
            project = require(client.get(f"/rest/api/3/project/{PROJECT}"), "Project lookup")
            issue_types = {item["name"].lower(): item["id"] for item in project.get("issueTypes", [])}
            if "epic" not in issue_types or "story" not in issue_types:
                raise SystemExit("AIDP must provide Epic and Story issue types before roadmap creation.")

            versions = require(client.get(f"/rest/api/3/project/{PROJECT}/versions"), "Version lookup")
            version_by_name = {item["name"]: item for item in versions}
            for phase in ROADMAP:
                if phase["version"] not in version_by_name:
                    version_by_name[phase["version"]] = require(
                        client.post(
                            "/rest/api/3/version",
                            json={
                                "projectId": int(project["id"]),
                                "name": phase["version"],
                                "description": phase["goal"],
                                "startDate": phase["start"],
                                "releaseDate": phase["release"],
                                "released": False,
                            },
                        ),
                        f"Create version {phase['version']}",
                    )

            search = require(
                client.get(
                    "/rest/api/3/search/jql",
                    params={
                        "jql": f'project = {PROJECT} AND labels = "axiom-roadmap"',
                        "fields": "summary,issuetype,parent",
                        "maxResults": 100,
                    },
                ),
                "Roadmap issue lookup",
            )
            existing = {item["fields"]["summary"]: item for item in search.get("issues", [])}
            created_epics = created_stories = 0
            for phase_number, phase in enumerate(ROADMAP, start=1):
                version = version_by_name[phase["version"]]
                epic = existing.get(phase["epic"])
                if not epic:
                    epic = require(
                        client.post(
                            "/rest/api/3/issue",
                            json={
                                "fields": {
                                    "project": {"key": PROJECT},
                                    "issuetype": {"id": issue_types["epic"]},
                                    "summary": phase["epic"],
                                    "description": adf(phase["goal"]),
                                    "labels": ["axiom-roadmap", f"phase-{phase_number}"],
                                    "fixVersions": [{"id": version["id"]}],
                                    "duedate": phase["release"],
                                    "priority": {"name": "High"},
                                }
                            },
                        ),
                        f"Create epic {phase['epic']}",
                    )
                    created_epics += 1
                for story_number, summary in enumerate(phase["stories"], start=1):
                    if summary in existing:
                        continue
                    require(
                        client.post(
                            "/rest/api/3/issue",
                            json={
                                "fields": {
                                    "project": {"key": PROJECT},
                                    "issuetype": {"id": issue_types["story"]},
                                    "parent": {"key": epic["key"]},
                                    "summary": summary,
                                    "description": adf(
                                        f"Roadmap story {phase_number}.{story_number}. Outcome: {phase['goal']}"
                                    ),
                                    "labels": ["axiom-roadmap", f"phase-{phase_number}"],
                                    "fixVersions": [{"id": version["id"]}],
                                    "duedate": phase["release"],
                                    "priority": {"name": "Medium"},
                                }
                            },
                        ),
                        f"Create story {summary}",
                    )
                    created_stories += 1
            print(
                f"AIDP roadmap ready: {len(ROADMAP)} phases, "
                f"{created_epics} epics created, {created_stories} stories created."
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
