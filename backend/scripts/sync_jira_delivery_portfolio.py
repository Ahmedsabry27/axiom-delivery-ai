"""Project real Jira Scrum data into canonical Sprint and Release repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.database.models.delivery import (
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
)
from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

TENANT = "axiom-demo"
LEGACY_PROJECTS = {
    "CUSTAI": "Digital Experience Squad",
    "OPSINT": "Operations Automation Squad",
    "AIGOV": "AI Governance Squad",
}


def stable(kind, value):
    return str(uuid5(NAMESPACE_URL, f"axiom:{TENANT}:jira:{kind}:{value}"))


def day(value):
    try:
        return (
            datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            if value
            else None
        )
    except ValueError:
        return None


def get(client, path, params=None):
    response = client.get(path, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"Jira read failed at {path} ({response.status_code})")
    return response.json()


def document_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(document_text(item) for item in value)
    if isinstance(value, dict):
        own = str(value.get("text") or "")
        nested = document_text(value.get("content") or [])
        return f"{own} {nested}".strip()
    return ""


def jira_hierarchy(client):
    """Discover Axiom hierarchy metadata directly from Jira project properties."""
    projects = []
    start_at = 0
    while True:
        page = get(
            client,
            "/rest/api/3/project/search",
            {"startAt": start_at, "maxResults": 50},
        )
        values = page.get("values", [])
        projects.extend(values)
        if page.get("isLast", start_at + len(values) >= page.get("total", 0)):
            break
        start_at += len(values)
    hierarchy = []
    for project in projects:
        response = client.get(
            f"/rest/api/3/project/{project['key']}/properties/axiom-hierarchy"
        )
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            raise RuntimeError(
                f"Jira hierarchy read failed for {project['key']} ({response.status_code})"
            )
        value = response.json().get("value") or {}
        if value.get("entityType") in {"PORTFOLIO", "PROJECT"}:
            hierarchy.append({"jira": project, "hierarchy": value})
    return hierarchy


def upsert(db, model, identifier, **values):
    row = db.query(model).filter_by(tenant_id=TENANT, id=identifier).first()
    if row is None:
        row = model(tenant_id=TENANT, id=identifier, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
    return row


def common(name, status, external_id, url, metadata=None):
    return dict(
        name=name,
        status=status,
        source_system="JIRA",
        external_id=str(external_id),
        source_url=url,
        owner_id="Ahmed Sabry",
        created_by="jira-sync",
        updated_by="jira-sync",
        record_metadata={"live": True, **(metadata or {})},
    )


def main():
    db = SessionLocal()
    try:
        connection = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id=TENANT, connector_type="jira")
            .one()
        )
        credential = secret_provider.resolve(connection.secret_ref)
        with httpx.Client(
            base_url=connection.base_url,
            auth=(credential["email"], credential["api_token"]),
            headers={"Accept": "application/json"},
            timeout=30,
            follow_redirects=False,
        ) as client:
            me = get(client, "/rest/api/3/myself")
            fields = get(client, "/rest/api/3/field")
            points_field = next(
                (
                    field["id"]
                    for field in fields
                    if field.get("name", "").lower()
                    in {"story points", "story point estimate"}
                ),
                None,
            )
            portfolio_id = stable("portfolio", "enterprise-ai-delivery")
            programme_id = stable("programme", "jira-scrum-portfolio")
            upsert(
                db,
                DeliveryPortfolio,
                portfolio_id,
                **common(
                    "Enterprise AI Delivery Portfolio",
                    "ACTIVE",
                    "jira-enterprise-ai-delivery",
                    connection.base_url,
                    {"provider": "Jira Cloud", "hierarchy_source": "legacy"},
                ),
            )
            db.flush()
            upsert(
                db,
                DeliveryProgramme,
                programme_id,
                portfolio_id=portfolio_id,
                **common(
                    "AI Transformation Programme",
                    "ACTIVE",
                    "jira-ai-transformation",
                    connection.base_url,
                    {"provider": "Jira Cloud", "hierarchy_source": "legacy"},
                ),
            )
            db.flush()
            hierarchy = jira_hierarchy(client)
            portfolio_ids = {}
            for entry in hierarchy:
                value = entry["hierarchy"]
                if value.get("entityType") != "PORTFOLIO":
                    continue
                key = entry["jira"]["key"]
                identifier = stable("portfolio", key)
                portfolio_ids[key] = identifier
                upsert(
                    db,
                    DeliveryPortfolio,
                    identifier,
                    **common(
                        value.get("portfolioName") or entry["jira"]["name"],
                        "ACTIVE",
                        key,
                        f"{connection.base_url}/browse/{key}",
                        {
                            "provider": "Jira Cloud",
                            "hierarchy_source": "axiom-hierarchy",
                            "strategic_theme": value.get("strategicTheme"),
                        },
                    ),
                )
            db.flush()
            discovered = []
            programme_ids = {}
            for entry in hierarchy:
                value = entry["hierarchy"]
                if value.get("entityType") != "PROJECT":
                    continue
                key = entry["jira"]["key"]
                portfolio_key = value.get("portfolioKey")
                parent_id = portfolio_ids.get(portfolio_key)
                if not parent_id:
                    parent_id = stable("portfolio", portfolio_key or "unmapped-jira")
                    portfolio_ids[portfolio_key] = parent_id
                    upsert(
                        db,
                        DeliveryPortfolio,
                        parent_id,
                        **common(
                            value.get("portfolioName") or "Unmapped Jira Portfolio",
                            "ACTIVE",
                            portfolio_key or "jira-unmapped",
                            connection.base_url,
                            {
                                "provider": "Jira Cloud",
                                "hierarchy_source": "axiom-hierarchy",
                            },
                        ),
                    )
                    db.flush()
                programme_name = value.get("programmeName") or "Jira Delivery Programme"
                programme_key = (portfolio_key, programme_name)
                discovered_programme_id = programme_ids.get(programme_key)
                if not discovered_programme_id:
                    discovered_programme_id = stable(
                        "programme", f"{portfolio_key}:{programme_name}"
                    )
                    programme_ids[programme_key] = discovered_programme_id
                    upsert(
                        db,
                        DeliveryProgramme,
                        discovered_programme_id,
                        portfolio_id=parent_id,
                        **common(
                            programme_name,
                            "ACTIVE",
                            value.get("programmeId")
                            or f"{portfolio_key}:{programme_name}",
                            connection.base_url,
                            {
                                "provider": "Jira Cloud",
                                "hierarchy_source": "axiom-hierarchy",
                                "portfolio_key": portfolio_key,
                            },
                        ),
                    )
                    db.flush()
                discovered.append(
                    (key, f"{entry['jira']['name']} Squad", discovered_programme_id)
                )
            project_specs = [
                (key, team_name, programme_id)
                for key, team_name in LEGACY_PROJECTS.items()
            ] + discovered
            counts = {
                "portfolios": len(portfolio_ids),
                "programmes": len(programme_ids),
                "projects": 0,
                "teams": 0,
                "sprints": 0,
                "releases": 0,
                "work_items": 0,
            }
            for key, team_name, project_programme_id in project_specs:
                project_data = get(client, f"/rest/api/3/project/{key}")
                project_id = stable("project", key)
                project = upsert(
                    db,
                    DeliveryProject,
                    project_id,
                    programme_id=project_programme_id,
                    **common(
                        project_data["name"],
                        "ACTIVE",
                        key,
                        f"{connection.base_url}/browse/{key}",
                        {
                            "jira_project_id": project_data["id"],
                            "key": key,
                            "hierarchy_source": "legacy"
                            if key in LEGACY_PROJECTS
                            else "axiom-hierarchy",
                        },
                    ),
                )
                counts["projects"] += 1
                db.flush()
                boards = get(
                    client,
                    "/rest/agile/1.0/board",
                    {"projectKeyOrId": key, "type": "scrum", "maxResults": 50},
                ).get("values", [])
                if not boards:
                    continue
                board = boards[0]
                team_id = stable("team", board["id"])
                upsert(
                    db,
                    DeliveryTeam,
                    team_id,
                    project_id=project.id,
                    active=True,
                    capacity=40,
                    **common(
                        team_name,
                        "ACTIVE",
                        board["id"],
                        f"{connection.base_url}/jira/software/projects/{key}/boards/{board['id']}",
                        {"board_name": board["name"], "board_type": board["type"]},
                    ),
                )
                counts["teams"] += 1
                db.flush()
                sprint_values = get(
                    client,
                    f"/rest/agile/1.0/board/{board['id']}/sprint",
                    {"state": "active,future,closed", "maxResults": 100},
                ).get("values", [])
                issue_sprint = {}
                for value in sprint_values:
                    sprint_id = stable("sprint", value["id"])
                    for issue in get(
                        client,
                        f"/rest/agile/1.0/sprint/{value['id']}/issue",
                        {"fields": "key", "maxResults": 100},
                    ).get("issues", []):
                        issue_sprint[issue["key"]] = sprint_id
                    state = {
                        "future": "PLANNED",
                        "active": "ACTIVE",
                        "closed": "COMPLETED",
                    }.get(value.get("state"), "PLANNED")
                    upsert(
                        db,
                        DeliverySprint,
                        sprint_id,
                        project_id=project.id,
                        team_id=team_id,
                        goal=value.get("goal") or "Jira sprint goal not specified",
                        start_date=day(value.get("startDate")),
                        end_date=day(value.get("endDate")),
                        original_committed_points=0,
                        completed_original_points=0,
                        completed_points=0,
                        scope_added_points=0,
                        scope_removed_points=0,
                        **common(
                            value["name"],
                            state,
                            value["id"],
                            f"{connection.base_url}/jira/software/projects/{key}/boards/{board['id']}",
                            {"jira_state": value.get("state"), "board_id": board["id"]},
                        ),
                    )
                    counts["sprints"] += 1
                for value in get(client, f"/rest/api/3/project/{key}/versions"):
                    if value.get("archived"):
                        continue
                    release_id = stable("release", value["id"])
                    lifecycle = "DEPLOYED" if value.get("released") else "PLANNING"
                    planned = day(value.get("releaseDate"))
                    contract = {
                        "releaseId": str(value["id"]),
                        "name": value["name"],
                        "version": value["name"],
                        "releaseType": "Jira Fix Version",
                        "environment": "PROD",
                        "targetDate": planned.isoformat() if planned else None,
                        "releaseOwner": "Ahmed Sabry",
                        "businessOwner": "Product Leadership",
                        "technicalOwner": team_name,
                        "lifecycle": lifecycle,
                        "readinessScore": 0,
                        "recommendation": "INSUFFICIENT EVIDENCE",
                        "decisionOwner": "Release Governance Board",
                        "criteria": [],
                        "blockers": [],
                        "risks": [],
                        "conditions": [],
                        "exceptions": [],
                        "evidence": [],
                        "phase": lifecycle,
                        "changeReference": f"JIRA-{key}-{value['id']}",
                        "statusLabel": lifecycle,
                        "sourceSystem": "JIRA",
                        "jiraProject": key,
                    }
                    upsert(
                        db,
                        DeliveryRelease,
                        release_id,
                        project_id=project.id,
                        planned_date=planned,
                        readiness_score=0,
                        **common(
                            value["name"],
                            lifecycle,
                            value["id"],
                            f"{connection.base_url}/plugins/servlet/project-config/{key}/versions",
                            {"release_contract": contract},
                        ),
                    )
                    counts["releases"] += 1
                requested = (
                    "summary,status,issuetype,parent,assignee,priority,fixVersions,issuelinks,description,labels"
                    + (f",{points_field}" if points_field else "")
                )
                issues = get(
                    client,
                    "/rest/api/3/search/jql",
                    {
                        "jql": f'project = {key} AND labels = "axiom-real-portfolio" ORDER BY created ASC',
                        "fields": requested,
                        "maxResults": 100,
                    },
                ).get("issues", [])
                totals = {}
                for index, issue in enumerate(issues, start=1):
                    data = issue["fields"]
                    if data["issuetype"]["name"].lower() == "epic":
                        continue
                    sprint_id = issue_sprint.get(issue["key"])
                    raw = data.get(points_field) if points_field else None
                    points = float(raw or [3, 5, 8][(index - 1) % 3])
                    done = data["status"].get("statusCategory", {}).get("key") == "done"
                    blocked = any(
                        link.get("inwardIssue")
                        and "block"
                        in (link.get("type", {}).get("inward") or "").lower()
                        for link in data.get("issuelinks", [])
                    )
                    assignee = data.get("assignee") or {}
                    description_text = document_text(data.get("description")).lower()
                    assignee_id = (
                        "local-developer"
                        if assignee.get("accountId") == me.get("accountId")
                        else assignee.get("displayName")
                    )
                    upsert(
                        db,
                        DeliveryWorkItem,
                        stable("work-item", issue["key"]),
                        project_id=project.id,
                        sprint_id=sprint_id,
                        item_kind=data["issuetype"]["name"].upper(),
                        story_points=points,
                        assignee_id=assignee_id,
                        goal_critical=data.get("priority", {}).get("name")
                        in {"Highest", "High"},
                        blocked=blocked,
                        added_after_start=False,
                        removed_after_start=False,
                        completed_at=datetime.now(UTC) if done else None,
                        **common(
                            data["summary"],
                            data["status"]["name"].upper().replace(" ", "_"),
                            issue["key"],
                            f"{connection.base_url}/browse/{issue['key']}",
                            {
                                "parent": (data.get("parent") or {}).get("key"),
                                "fix_versions": [
                                    v["name"] for v in data.get("fixVersions", [])
                                ],
                                "issue_links": data.get("issuelinks", []),
                                "jira_assignee": assignee.get("displayName"),
                                "acceptanceCriteria": (
                                    "acceptance criteria" in description_text
                                    or "acceptance-criteria-defined"
                                    in (data.get("labels") or [])
                                ),
                            },
                        ),
                    )
                    counts["work_items"] += 1
                    if sprint_id:
                        bucket = totals.setdefault(sprint_id, [0, 0])
                        bucket[0] += points
                        bucket[1] += points if done else 0
                db.flush()
                for sprint_id, (committed, completed) in totals.items():
                    sprint = (
                        db.query(DeliverySprint)
                        .filter_by(tenant_id=TENANT, id=sprint_id)
                        .one()
                    )
                    sprint.original_committed_points = committed
                    sprint.completed_original_points = completed
                    sprint.completed_points = completed
            db.commit()
            print(f"Jira delivery projection succeeded: {counts}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
