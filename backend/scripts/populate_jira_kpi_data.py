"""Populate live Jira projects with idempotent delivery evidence for KPI calculation."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

TENANT = "axiom-demo"
LEGACY_KEYS = {"CUSTAI", "OPSINT", "AIGOV"}
STORIES = (
    ("Confirm measurable outcome and acceptance criteria", 5, "High"),
    ("Deliver governed integration foundation", 8, "High"),
    ("Validate end-to-end operational workflow", 5, "Medium"),
    ("Complete security and resilience controls", 8, "High"),
    ("Resolve cross-team release dependency", 5, "Highest"),
    ("Prepare release evidence and stakeholder sign-off", 3, "Medium"),
)
SPRINTS = (
    ("KPI A", "Deliver a measurable integrated foundation", "2026-07-13T08:00:00.000Z", "2026-07-26T17:00:00.000Z"),
    ("KPI B", "Complete controls and release readiness", "2026-07-27T08:00:00.000Z", "2026-08-09T17:00:00.000Z"),
)


def adf(text: str) -> dict:
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def require(response: httpx.Response, operation: str, accepted=(200, 201, 204)) -> dict:
    if response.status_code not in accepted:
        try:
            body = response.json()
            errors = body.get("errorMessages") or list((body.get("errors") or {}).values())
        except ValueError:
            errors = []
        raise RuntimeError(f"{operation} failed ({response.status_code}): {'; '.join(map(str, errors)) or 'Provider rejected request'}")
    return response.json() if response.content else {}


def transition(client: httpx.Client, issue_key: str, target: str) -> bool:
    issue = require(client.get(f"/rest/api/3/issue/{issue_key}", params={"fields": "status"}), f"Read status {issue_key}")
    if issue["fields"]["status"].get("statusCategory", {}).get("key") == target:
        return False
    transitions = require(client.get(f"/rest/api/3/issue/{issue_key}/transitions", params={"expand": "transitions.fields"}), f"Read transitions {issue_key}").get("transitions", [])
    selected = next((row for row in transitions if row.get("to", {}).get("statusCategory", {}).get("key") == target), None)
    if not selected and target == "done":
        transition(client, issue_key, "indeterminate")
        transitions = require(client.get(f"/rest/api/3/issue/{issue_key}/transitions"), f"Reload transitions {issue_key}").get("transitions", [])
        selected = next((row for row in transitions if row.get("to", {}).get("statusCategory", {}).get("key") == target), None)
    if not selected:
        return False
    require(client.post(f"/rest/api/3/issue/{issue_key}/transitions", json={"transition": {"id": selected["id"]}}), f"Transition {issue_key}")
    return True


def main() -> None:
    db = SessionLocal()
    try:
        connection = db.query(IntegrationConnection).filter_by(tenant_id=TENANT, connector_type="jira").one()
        credential = secret_provider.resolve(connection.secret_ref)
        counts = {"projects": 0, "stories_created": 0, "transitions": 0, "sprints_created": 0, "links_created": 0, "releases_created": 0}
        with httpx.Client(base_url=connection.base_url, auth=(credential["email"], credential["api_token"]), headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30) as client:
            fields = require(client.get("/rest/api/3/field"), "Field lookup")
            points_field = next((row["id"] for row in fields if row.get("name", "").lower() in {"story points", "story point estimate"}), None)
            projects = require(client.get("/rest/api/3/project/search", params={"maxResults": 100}), "Project lookup").get("values", [])
            selected = []
            for project in projects:
                prop = client.get(f"/rest/api/3/project/{project['key']}/properties/axiom-hierarchy")
                if project["key"] in LEGACY_KEYS or (prop.status_code == 200 and prop.json().get("value", {}).get("entityType") == "PROJECT"):
                    selected.append(project)
            link_types = require(client.get("/rest/api/3/issueLinkType"), "Link type lookup").get("issueLinkTypes", [])
            blocks_type = next((row["name"] for row in link_types if row.get("name", "").lower() == "blocks"), None)
            for project in selected:
                key = project["key"]
                detail = require(client.get(f"/rest/api/3/project/{key}"), f"Project {key}")
                issue_types = {row["name"].lower(): row["id"] for row in detail.get("issueTypes", [])}
                story_type = issue_types.get("story") or issue_types.get("task")
                existing = require(client.get("/rest/api/3/search/jql", params={"jql": f'project = {key} AND labels = "axiom-real-portfolio" ORDER BY created ASC', "fields": "summary,status,issuelinks,issuetype", "maxResults": 100}), f"Issues {key}").get("issues", [])
                by_summary = {row["fields"]["summary"]: row for row in existing}
                versions = require(client.get(f"/rest/api/3/project/{key}/versions"), f"Versions {key}")
                version_name = f"{key} Outcome Release 1.0"
                version = next((row for row in versions if row["name"] == version_name), None)
                if not version:
                    version = require(client.post("/rest/api/3/version", json={"projectId": int(detail["id"]), "name": version_name, "description": "Evidence-backed outcome release", "releaseDate": "2026-09-30", "released": False}), f"Create release {key}")
                    counts["releases_created"] += 1
                story_keys = []
                if key in LEGACY_KEYS and len(existing) >= 6:
                    story_keys = [
                        row["key"]
                        for row in existing
                        if row["fields"].get("status")
                        and row["fields"].get("issuetype", {}).get("name", "").lower() != "epic"
                    ][:6]
                else:
                    for index, (base_summary, points, priority) in enumerate(STORIES, start=1):
                        summary = f"{key}: {base_summary}"
                        issue = by_summary.get(summary)
                        if not issue:
                            issue_fields = {"project": {"key": key}, "issuetype": {"id": story_type}, "summary": summary, "description": adf(f"Real Jira delivery evidence for {project['name']}."), "labels": ["axiom-real-portfolio", "axiom-kpi-evidence"], "priority": {"name": priority}, "fixVersions": [{"id": version["id"]}]}
                            if points_field:
                                issue_fields[points_field] = points
                            issue = require(client.post("/rest/api/3/issue", json={"fields": issue_fields}), f"Create story {summary}")
                            counts["stories_created"] += 1
                        story_keys.append(issue["key"])
                boards = require(client.get("/rest/agile/1.0/board", params={"projectKeyOrId": key, "type": "scrum", "maxResults": 50}), f"Board {key}").get("values", [])
                if not boards:
                    continue
                board_id = boards[0]["id"]
                sprint_rows = require(client.get(f"/rest/agile/1.0/board/{board_id}/sprint", params={"state": "active,future,closed", "maxResults": 100}), f"Sprints {key}").get("values", [])
                sprint_map = {row["name"]: row for row in sprint_rows}
                for index, (base_name, goal, start, end) in enumerate(SPRINTS):
                    name = f"{key} {base_name}"
                    sprint = sprint_map.get(name)
                    if not sprint:
                        sprint = require(client.post("/rest/agile/1.0/sprint", json={"name": name, "goal": goal, "startDate": start, "endDate": end, "originBoardId": board_id}), f"Create sprint {name}")
                        counts["sprints_created"] += 1
                    assigned = story_keys[index * 3:(index + 1) * 3]
                    if assigned:
                        require(client.post(f"/rest/agile/1.0/sprint/{sprint['id']}/issue", json={"issues": assigned}), f"Assign sprint {name}")
                for issue_key in story_keys[:2]:
                    counts["transitions"] += int(transition(client, issue_key, "done"))
                for issue_key in story_keys[2:4]:
                    counts["transitions"] += int(transition(client, issue_key, "indeterminate"))
                if blocks_type and len(story_keys) >= 6:
                    blocked = require(client.get(f"/rest/api/3/issue/{story_keys[5]}", params={"fields": "issuelinks"}), f"Links {story_keys[5]}")
                    links = blocked["fields"].get("issuelinks", [])
                    already = any((row.get("inwardIssue") or {}).get("key") == story_keys[4] for row in links)
                    if not already:
                        require(client.post("/rest/api/3/issueLink", json={"type": {"name": blocks_type}, "outwardIssue": {"key": story_keys[4]}, "inwardIssue": {"key": story_keys[5]}}), f"Create blocker {key}")
                        counts["links_created"] += 1
                counts["projects"] += 1
                print(f"KPI evidence ready: {key} ({len(story_keys)} stories)")
        print(f"Jira KPI evidence completed at {datetime.now(UTC).isoformat()}: {counts}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
