"""Run a bounded read-only Jira import and replace obsolete simulator lineage."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.database.models.integration import (
    IntegrationConnection,
    IntegrationQuarantine,
    IntegrationSourceRecord,
    IntegrationSyncRun,
)
from app.database.session import SessionLocal
from app.integrations.jira import JiraConnector
from app.integrations.secrets import secret_provider


async def main() -> None:
    db = SessionLocal()
    try:
        row = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id="axiom-demo", connector_type="jira")
            .one()
        )
        if (
            row.auth_type != "api_token"
            or not str(row.secret_ref).startswith(
                ("keychain://", "env://", "aws-secrets://")
            )
            or row.base_url != "https://ahmedsabry27.atlassian.net"
        ):
            raise SystemExit("Jira is not configured for a live API-token connection.")
        connector = JiraConnector()
        credential = secret_provider.resolve(row.secret_ref)
        projects_page = await connector.execute_tool(
            row, "jira.get_projects", {}, credential
        )
        project_keys = [
            str(project["key"])
            for project in projects_page.get("values", [])
            if project.get("key")
        ]
        if not project_keys:
            raise SystemExit(
                "No accessible Jira projects were returned; nothing changed."
            )
        scoped_jql = (
            "project in ("
            + ",".join(f'"{key}"' for key in project_keys)
            + ") order by updated DESC"
        )
        boards: dict[str, dict] = {}
        for project_key in project_keys:
            page = await connector._request(
                row,
                credential,
                "GET",
                "/rest/agile/1.0/board",
                params={"projectKeyOrId": project_key, "maxResults": 100},
            )
            for board in page.get("values", []):
                boards[str(board.get("id"))] = board
        sprints: dict[str, tuple[dict, str]] = {}
        for board_id, board in boards.items():
            if str(board.get("type", "")).casefold() != "scrum":
                continue
            page = await connector._request(
                row,
                credential,
                "GET",
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"maxResults": 100, "state": "active,future,closed"},
            )
            for sprint in page.get("values", []):
                sprints[str(sprint.get("id"))] = (sprint, board_id)
        issues_page = await connector.execute_tool(
            row,
            "jira.search_issues",
            {"jql": scoped_jql, "max_results": 100},
            credential,
        )
        now = datetime.now(UTC)
        run = IntegrationSyncRun(
            connection_id=row.id,
            tenant_id=row.tenant_id,
            mode="FULL",
            trigger="MANUAL",
            status="RUNNING",
            configuration_version=row.lock_version,
            mapping_version=1,
            correlation_ref=f"jira-live-{uuid4().hex[:16]}",
            started_at=now,
        )
        db.add(run)
        db.flush()
        # These rows were explicitly labelled simulator data and must not appear as live Jira lineage.
        db.query(IntegrationSourceRecord).filter_by(
            connection_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        db.query(IntegrationQuarantine).filter_by(
            connection_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        imported = []
        for project in projects_page.get("values", []):
            imported.append(
                (
                    "project",
                    str(project.get("id")),
                    "Project",
                    str(project.get("key") or project.get("id")),
                    str(project.get("name") or project.get("key")),
                    {
                        "key": project.get("key"),
                        "project_type": project.get("projectTypeKey"),
                    },
                )
            )
        for board_id, board in boards.items():
            location = board.get("location") or {}
            imported.append(
                (
                    "board",
                    board_id,
                    "Team/project context",
                    board_id,
                    str(board.get("name") or f"Board {board_id}"),
                    {
                        "board_type": board.get("type"),
                        "project_key": location.get("projectKey"),
                        "project_name": location.get("projectName"),
                    },
                )
            )
        for sprint_id, (sprint, board_id) in sprints.items():
            imported.append(
                (
                    "sprint",
                    sprint_id,
                    "Sprint",
                    sprint_id,
                    str(sprint.get("name") or f"Sprint {sprint_id}"),
                    {
                        "board_id": board_id,
                        "state": sprint.get("state"),
                        "start_date": sprint.get("startDate"),
                        "end_date": sprint.get("endDate"),
                        "goal": sprint.get("goal"),
                    },
                )
            )
        for issue in issues_page.get("issues", []):
            fields = issue.get("fields") or {}
            issue_type = (fields.get("issuetype") or {}).get("name", "Work Item")
            canonical = "Defect" if issue_type.casefold() == "bug" else "Work Item"
            imported.append(
                (
                    "issue",
                    str(issue.get("id") or issue.get("key")),
                    canonical,
                    str(issue.get("key")),
                    str(fields.get("summary") or issue.get("key")),
                    {
                        "key": issue.get("key"),
                        "issue_type": issue_type,
                        "status": (fields.get("status") or {}).get("name"),
                        "priority": (fields.get("priority") or {}).get("name"),
                        "project_key": (fields.get("project") or {}).get("key"),
                    },
                )
            )
        for (
            entity_type,
            external_id,
            canonical_type,
            canonical_id,
            title,
            safe_payload,
        ) in imported:
            encoded = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"))
            db.add(
                IntegrationSourceRecord(
                    connection_id=row.id,
                    tenant_id=row.tenant_id,
                    provider="atlassian",
                    provider_tenant_id="ahmedsabry27.atlassian.net",
                    external_entity_type=entity_type,
                    external_entity_id=external_id,
                    canonical_entity_type=canonical_type,
                    canonical_entity_id=canonical_id,
                    source_version="live-1",
                    source_updated_at=now,
                    content_fingerprint=sha256(encoded.encode()).hexdigest(),
                    title=title,
                    source_url=(
                        f"{row.base_url}/browse/{canonical_id}"
                        if entity_type == "issue"
                        else f"{row.base_url}/secure/RapidBoard.jspa?rapidView={canonical_id}"
                        if entity_type == "board"
                        else row.base_url
                    ),
                    classification="INTERNAL",
                    data_status="CURRENT",
                    safe_payload=safe_payload,
                    first_synchronized_at=now,
                    last_synchronized_at=now,
                    last_successful_run_id=run.id,
                )
            )
        cursor = f"jira:{now.isoformat()}"
        run.status = "SUCCEEDED"
        run.cursor_end = cursor
        run.ended_at = now
        run.counters = {
            "discovered": len(imported),
            "created": len(imported),
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
            "quarantined": 0,
            "failed": 0,
        }
        row.configuration = {
            **row.configuration,
            "simulator": False,
            "provider_tenant_id": "ahmedsabry27.atlassian.net",
            "site_url": row.base_url,
            "sync_cursor": cursor,
            "source_scope": {"selection": "All accessible Jira projects"},
        }
        row.safe_metadata = {
            **row.safe_metadata,
            "mode": "LIVE",
            "last_sync_run_id": run.id,
            "project_count": len(projects_page.get("values", [])),
            "board_count": len(boards),
            "sprint_count": len(sprints),
            "live_source_records": len(imported),
        }
        db.commit()
        print(
            f"Live Jira synchronization succeeded: {len(imported)} source records imported."
        )
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
