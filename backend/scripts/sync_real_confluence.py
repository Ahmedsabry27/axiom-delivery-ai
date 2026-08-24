"""Configure and run a bounded read-only Confluence Cloud v2 import."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import httpx

from app.database.models.integration import (
    IntegrationConnection,
    IntegrationQuarantine,
    IntegrationSourceRecord,
    IntegrationSyncRun,
)
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

SITE = "https://ahmedsabry27.atlassian.net"


def request(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    response = client.get(path, params=params)
    if response.status_code != 200:
        raise SystemExit(
            f"Confluence read failed with HTTP {response.status_code}; nothing changed."
        )
    value = response.json()
    if not isinstance(value, dict):
        raise SystemExit("Confluence returned an invalid response; nothing changed.")
    return value


def parsed_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def main() -> None:
    db = SessionLocal()
    try:
        jira = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id="axiom-demo", connector_type="jira")
            .one()
        )
        row = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id="axiom-demo", connector_type="confluence")
            .one()
        )
        credential = secret_provider.resolve(jira.secret_ref)
        with httpx.Client(
            base_url=SITE,
            auth=(credential["email"], credential["api_token"]),
            headers={"Accept": "application/json"},
            timeout=20,
            follow_redirects=False,
        ) as client:
            spaces_page = request(client, "/wiki/api/v2/spaces", {"limit": 250})
            pages_page = request(
                client,
                "/wiki/api/v2/pages",
                {"limit": 250, "status": "current"},
            )
        spaces = spaces_page.get("results", [])
        pages = pages_page.get("results", [])
        now = datetime.now(UTC)
        run = IntegrationSyncRun(
            connection_id=row.id,
            tenant_id=row.tenant_id,
            mode="FULL",
            trigger="MANUAL",
            status="RUNNING",
            configuration_version=row.lock_version,
            mapping_version=1,
            correlation_ref=f"confluence-live-{uuid4().hex[:16]}",
            started_at=now,
        )
        db.add(run)
        db.flush()
        db.query(IntegrationSourceRecord).filter_by(
            connection_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        db.query(IntegrationQuarantine).filter_by(
            connection_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        imported: list[dict] = []
        for space in spaces:
            imported.append(
                {
                    "entity_type": "space",
                    "external_id": str(space.get("id")),
                    "canonical_type": "Knowledge Source",
                    "title": str(space.get("name") or space.get("key") or "Space"),
                    "version": str(space.get("status") or "current"),
                    "updated": parsed_time(space.get("createdAt"), now),
                    "source_url": f"{SITE}/wiki/spaces/{space.get('key')}",
                    "payload": {
                        "key": space.get("key"),
                        "type": space.get("type"),
                        "status": space.get("status"),
                    },
                }
            )
        for page in pages:
            version = page.get("version") or {}
            webui = (page.get("_links") or {}).get("webui")
            imported.append(
                {
                    "entity_type": "page",
                    "external_id": str(page.get("id")),
                    "canonical_type": "Evidence",
                    "title": str(page.get("title") or "Untitled page"),
                    "version": str(version.get("number") or 1),
                    "updated": parsed_time(
                        version.get("createdAt") or page.get("createdAt"), now
                    ),
                    "source_url": f"{SITE}{webui}"
                    if webui
                    else f"{SITE}/wiki/pages/{page.get('id')}",
                    "payload": {
                        "space_id": page.get("spaceId"),
                        "parent_id": page.get("parentId"),
                        "status": page.get("status"),
                        "author_id": page.get("authorId"),
                    },
                }
            )
        for item in imported:
            encoded = json.dumps(item["payload"], sort_keys=True, separators=(",", ":"))
            db.add(
                IntegrationSourceRecord(
                    connection_id=row.id,
                    tenant_id=row.tenant_id,
                    provider="atlassian",
                    provider_tenant_id="ahmedsabry27.atlassian.net",
                    external_entity_type=item["entity_type"],
                    external_entity_id=item["external_id"],
                    canonical_entity_type=item["canonical_type"],
                    canonical_entity_id=item["external_id"],
                    source_version=item["version"],
                    source_updated_at=item["updated"],
                    content_fingerprint=sha256(encoded.encode()).hexdigest(),
                    title=item["title"],
                    source_url=item["source_url"],
                    classification="INTERNAL",
                    data_status="CURRENT",
                    safe_payload=item["payload"],
                    first_synchronized_at=now,
                    last_synchronized_at=now,
                    last_successful_run_id=run.id,
                )
            )
        cursor = f"confluence:{now.isoformat()}"
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
        row.display_name = "Ahmed Sabry Confluence Cloud"
        row.base_url = SITE
        row.auth_type = "api_token"
        row.secret_ref = jira.secret_ref
        row.configuration = {
            "simulator": False,
            "provider_tenant_id": "ahmedsabry27.atlassian.net",
            "site_url": SITE,
            "sync_cursor": cursor,
            "source_scope": {"selection": "All accessible Confluence spaces"},
            "sync_policy": {"mode": "FULL", "bounded_batch_size": 250},
        }
        row.safe_metadata = {
            "mode": "LIVE",
            "site": SITE,
            "space_count": len(spaces),
            "page_count": len(pages),
            "last_sync_run_id": run.id,
        }
        row.status = "CONNECTED"
        row.health_status = "healthy"
        row.enabled = True
        row.last_error_code = row.last_error_message_safe = None
        db.commit()
        print(
            f"Live Confluence synchronization succeeded: {len(spaces)} spaces and {len(pages)} pages imported."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
