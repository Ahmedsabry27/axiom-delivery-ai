"""Create an idempotent, realistic multi-project Scrum portfolio in Jira Cloud."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

PORTFOLIO = [
    {
        "key": "CUSTAI", "name": "Customer Experience AI", "team": "Digital Experience Squad",
        "description": "AI-assisted customer journeys, service automation, and experience insights.",
        "releases": [("CX AI Pilot", "2026-09-30"), ("CX AI General Availability", "2026-11-30")],
        "epics": [
            ("Conversational service assistant", ["Design grounded customer intent routing", "Build retrieval-backed service answers", "Add safe human handoff and escalation"]),
            ("Customer journey intelligence", ["Capture journey events and consent", "Detect customer friction signals", "Publish experience insight dashboard"]),
            ("Production experience controls", ["Implement response quality evaluation", "Add latency and cost monitoring", "Complete pilot go-live readiness review"]),
        ],
    },
    {
        "key": "OPSINT", "name": "Operations Intelligence", "team": "Operations Automation Squad",
        "description": "Operational prediction, exception management, and governed automation.",
        "releases": [("Operations Control Tower MVP", "2026-10-15"), ("Predictive Operations Release", "2026-12-15")],
        "epics": [
            ("Operational data foundation", ["Connect governed operational data feeds", "Normalize operational events and ownership", "Implement data-quality monitoring"]),
            ("Predictive exception management", ["Detect high-impact operational anomalies", "Prioritize exceptions using business impact", "Generate evidence-backed intervention proposals"]),
            ("Control tower experience", ["Build real-time operations overview", "Add exception drill-down and audit trail", "Validate production support model"]),
        ],
    },
    {
        "key": "AIGOV", "name": "Responsible AI Governance", "team": "AI Governance Squad",
        "description": "Enterprise controls for models, agents, approvals, evidence, and auditability.",
        "releases": [("Governance Baseline", "2026-09-20"), ("Enterprise Governance Release", "2026-11-20")],
        "epics": [
            ("Model and agent registry", ["Register governed models and ownership", "Register agents with risk classifications", "Track lifecycle approvals and exceptions"]),
            ("Policy and approval enforcement", ["Evaluate runtime policy before execution", "Route restricted actions for human approval", "Verify approved action outcomes"]),
            ("Audit and compliance evidence", ["Capture immutable execution evidence", "Build governance operations dashboard", "Produce release compliance evidence pack"]),
        ],
    },
]
SPRINTS = [
    ("Sprint 1 — Foundation", "Establish the minimum production-grade foundation", "2026-08-24T08:00:00.000Z", "2026-09-06T17:00:00.000Z"),
    ("S2 Integrated", "Deliver end-to-end integrated user outcomes", "2026-09-07T08:00:00.000Z", "2026-09-20T17:00:00.000Z"),
    ("S3 Release", "Harden, evidence, and prepare the first release", "2026-09-21T08:00:00.000Z", "2026-10-04T17:00:00.000Z"),
]


def adf(text: str) -> dict:
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def require(response: httpx.Response, operation: str, accepted=(200, 201)) -> dict:
    if response.status_code not in accepted:
        try:
            body = response.json(); errors = body.get("errorMessages") or list((body.get("errors") or {}).values())
        except ValueError:
            errors = []
        raise RuntimeError(f"{operation} failed ({response.status_code}): {'; '.join(map(str, errors)) or 'Provider rejected the request'}")
    return response.json() if response.content else {}


def main() -> None:
    db = SessionLocal()
    try:
        connection = db.query(IntegrationConnection).filter_by(tenant_id="axiom-demo", connector_type="jira").one()
        credential = secret_provider.resolve(connection.secret_ref)
        with httpx.Client(base_url=connection.base_url, auth=(credential["email"], credential["api_token"]), headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30, follow_redirects=False) as client:
            me = require(client.get("/rest/api/3/myself"), "Account lookup")
            fields = require(client.get("/rest/api/3/field"), "Field lookup")
            points_field = next((field["id"] for field in fields if field.get("name", "").lower() in {"story points", "story point estimate"}), None)
            total_projects = total_epics = total_stories = total_sprints = 0
            for project_number, spec in enumerate(PORTFOLIO, start=1):
                response = client.get(f"/rest/api/3/project/{spec['key']}")
                if response.status_code == 404:
                    project = require(client.post("/rest/api/3/project", json={
                        "key": spec["key"], "name": spec["name"], "projectTypeKey": "software",
                        "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-scrum-template",
                        "description": spec["description"], "leadAccountId": me["accountId"], "assigneeType": "PROJECT_LEAD",
                    }), f"Create project {spec['key']}")
                    total_projects += 1
                else:
                    project = require(response, f"Project lookup {spec['key']}")
                project = require(client.get(f"/rest/api/3/project/{spec['key']}"), f"Reload project {spec['key']}")
                types = {item["name"].lower(): item["id"] for item in project.get("issueTypes", [])}
                versions = require(client.get(f"/rest/api/3/project/{spec['key']}/versions"), "Version lookup")
                version_map = {item["name"]: item for item in versions}
                for version_name, release_date in spec["releases"]:
                    if version_name not in version_map:
                        version_map[version_name] = require(client.post("/rest/api/3/version", json={
                            "projectId": int(project["id"]), "name": version_name,
                            "description": f"Roadmap release for {spec['name']}", "releaseDate": release_date, "released": False,
                        }), f"Create release {version_name}")
                existing_result = require(client.get("/rest/api/3/search/jql", params={
                    "jql": f'project = {spec["key"]} AND labels = "axiom-real-portfolio"',
                    "fields": "summary,issuetype,parent", "maxResults": 100,
                }), f"Search issues {spec['key']}")
                existing = {issue["fields"]["summary"]: issue for issue in existing_result.get("issues", [])}
                story_keys: list[str] = []
                for epic_number, (epic_name, stories) in enumerate(spec["epics"], start=1):
                    epic = existing.get(epic_name)
                    if not epic:
                        epic = require(client.post("/rest/api/3/issue", json={"fields": {
                            "project": {"key": spec["key"]}, "issuetype": {"id": types["epic"]},
                            "summary": epic_name, "description": adf(f"Strategic delivery epic for {spec['name']}."),
                            "labels": ["axiom-real-portfolio", f"portfolio-project-{project_number}"],
                            "fixVersions": [{"id": version_map[spec["releases"][0 if epic_number < 3 else 1][0]]["id"]}],
                            "priority": {"name": "High"},
                        }}), f"Create epic {epic_name}")
                        total_epics += 1
                    for story_number, summary in enumerate(stories, start=1):
                        story = existing.get(summary)
                        if not story:
                            story_fields = {
                                "project": {"key": spec["key"]}, "issuetype": {"id": types["story"]},
                                "parent": {"key": epic["key"]}, "summary": summary,
                                "description": adf(f"As the {spec['team']}, we need to {summary.lower()} so that the roadmap outcome is measurable and releasable."),
                                "labels": ["axiom-real-portfolio", f"sprint-{epic_number}"],
                                "fixVersions": [{"id": version_map[spec["releases"][0 if epic_number < 3 else 1][0]]["id"]}],
                                "priority": {"name": "High" if story_number == 1 else "Medium"},
                            }
                            if points_field:
                                story_fields[points_field] = [8, 5, 3][story_number - 1]
                            story = require(client.post("/rest/api/3/issue", json={"fields": story_fields}), f"Create story {summary}")
                            total_stories += 1
                        story_keys.append(story["key"])
                boards = require(client.get("/rest/agile/1.0/board", params={"projectKeyOrId": spec["key"], "type": "scrum", "maxResults": 50}), f"Board lookup {spec['key']}").get("values", [])
                if not boards:
                    raise RuntimeError(f"Jira did not provision a Scrum board for {spec['key']}")
                board_id = boards[0]["id"]
                existing_sprints = require(client.get(f"/rest/agile/1.0/board/{board_id}/sprint", params={"state": "active,future,closed", "maxResults": 100}), f"Sprint lookup {spec['key']}").get("values", [])
                sprint_map = {sprint["name"]: sprint for sprint in existing_sprints}
                for sprint_number, (base_name, goal, start, end) in enumerate(SPRINTS, start=1):
                    name = f"{spec['key']} {base_name}"
                    sprint = sprint_map.get(name)
                    if not sprint:
                        sprint = require(client.post("/rest/agile/1.0/sprint", json={"name": name, "goal": goal, "startDate": start, "endDate": end, "originBoardId": board_id}), f"Create sprint {name}")
                        total_sprints += 1
                    assigned = story_keys[(sprint_number - 1) * 3 : sprint_number * 3]
                    if assigned:
                        require(client.post(f"/rest/agile/1.0/sprint/{sprint['id']}/issue", json={"issues": assigned}), f"Assign stories to {name}", accepted=(204,))
                print(f"Ready: {spec['key']} | {spec['name']} | board {board_id}")
            print(f"Real Jira Scrum portfolio ready: {total_projects} projects, {total_epics} epics, {total_stories} stories, {total_sprints} sprints created at {datetime.now(UTC).isoformat()}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
