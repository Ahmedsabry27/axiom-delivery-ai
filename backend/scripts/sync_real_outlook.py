"""Run a bounded, read-only Microsoft Graph calendar synchronization."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.database.models.integration import (
    IntegrationConnection,
    IntegrationSourceRecord,
    IntegrationSyncRun,
    ProviderAuthorization,
)
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider

GRAPH = "https://graph.microsoft.com/v1.0"
CLIENT_ID = os.getenv("MICROSOFT_GRAPH_CLIENT_ID", "dbde8708-816a-46d7-a161-ad1a1a6be55d")
SCOPES = "openid profile offline_access User.Read Calendars.Read"


def parse_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def graph_get(client: httpx.Client, url: str, params: dict | None = None) -> dict:
    response = client.get(url, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"Microsoft Graph read failed with HTTP {response.status_code}")
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Microsoft Graph returned an invalid response")
    return result


def paged(client: httpx.Client, url: str, params: dict | None = None, limit: int = 1000) -> list[dict]:
    rows: list[dict] = []
    next_url: str | None = url
    next_params = params
    while next_url and len(rows) < limit:
        page = graph_get(client, next_url, next_params)
        rows.extend(item for item in page.get("value", []) if isinstance(item, dict))
        next_url = page.get("@odata.nextLink")
        next_params = None
    return rows[:limit]


def main() -> None:
    db = SessionLocal()
    try:
        row = db.query(IntegrationConnection).filter_by(
            tenant_id="axiom-demo", connector_type="outlook_calendar"
        ).one()
        account_id = (row.configuration or {}).get("provider_tenant_id")
        auth = db.query(ProviderAuthorization).filter_by(
            tenant_id=row.tenant_id, provider="microsoft", provider_tenant_id=account_id
        ).one()
        credential = secret_provider.resolve(auth.secret_ref)
        headers = {
            "Authorization": f"Bearer {credential['access_token']}",
            "Accept": "application/json",
            "Prefer": 'outlook.timezone="UTC"',
        }
        with httpx.Client(headers=headers, timeout=30, follow_redirects=False) as client:
            calendars = paged(client, f"{GRAPH}/me/calendars", {"$top": 100})
            start = datetime.now(UTC) - timedelta(days=30)
            end = datetime.now(UTC) + timedelta(days=90)
            events: list[tuple[str, dict]] = []
            for calendar in calendars:
                calendar_id = str(calendar.get("id") or "")
                if not calendar_id:
                    continue
                values = paged(
                    client,
                    f"{GRAPH}/me/calendars/{quote(calendar_id, safe='')}/calendarView",
                    {
                        "startDateTime": start.isoformat(),
                        "endDateTime": end.isoformat(),
                        "$top": 250,
                        "$select": "id,subject,start,end,organizer,attendees,isAllDay,isCancelled,isOnlineMeeting,onlineMeetingProvider,onlineMeeting,webLink,lastModifiedDateTime,seriesMasterId,type,showAs,sensitivity,location",
                    },
                )
                events.extend((calendar_id, event) for event in values)

        now = datetime.now(UTC)
        prior = db.query(IntegrationSyncRun).filter_by(
            connection_id=row.id, tenant_id=row.tenant_id, status="SUCCEEDED"
        ).order_by(IntegrationSyncRun.started_at.desc()).first()
        run = IntegrationSyncRun(
            connection_id=row.id,
            tenant_id=row.tenant_id,
            mode="INCREMENTAL",
            trigger="MANUAL",
            status="RUNNING",
            configuration_version=row.lock_version,
            mapping_version=1,
            cursor_start=prior.cursor_end if prior else None,
            correlation_ref=f"outlook-live-{uuid4().hex[:16]}",
            started_at=now,
        )
        db.add(run)
        db.flush()
        imported: list[dict] = []
        for calendar in calendars:
            calendar_id = str(calendar.get("id") or "")
            if calendar_id:
                imported.append({
                    "type": "calendar", "id": calendar_id, "canonical": "Calendar",
                    "title": str(calendar.get("name") or "Calendar"),
                    "version": str(calendar.get("changeKey") or "1"), "updated": now,
                    "url": None,
                    "payload": {"name": calendar.get("name"), "can_edit": calendar.get("canEdit"), "is_default": calendar.get("isDefaultCalendar"), "color": calendar.get("color")},
                })
        series_seen: set[str] = set()
        for calendar_id, event in events:
            event_id = str(event.get("id") or "")
            if not event_id:
                continue
            start_value = (event.get("start") or {}).get("dateTime")
            organizer = ((event.get("organizer") or {}).get("emailAddress") or {})
            attendees = event.get("attendees") or []
            payload = {
                "calendar_id": calendar_id,
                "start": event.get("start"), "end": event.get("end"),
                "organizer": {"name": organizer.get("name"), "address": organizer.get("address")},
                "attendee_count": len(attendees), "is_all_day": event.get("isAllDay"),
                "is_cancelled": event.get("isCancelled"), "is_online_meeting": event.get("isOnlineMeeting"),
                "online_meeting_provider": event.get("onlineMeetingProvider"), "show_as": event.get("showAs"),
                "join_url": (event.get("onlineMeeting") or {}).get("joinUrl"),
                "sensitivity": event.get("sensitivity"), "location": (event.get("location") or {}).get("displayName"),
                "series_master_id": event.get("seriesMasterId"), "type": event.get("type"),
            }
            imported.append({
                "type": "event", "id": event_id, "canonical": "Meeting",
                "title": str(event.get("subject") or "Untitled event"),
                "version": str(event.get("lastModifiedDateTime") or "1"),
                "updated": parse_time(event.get("lastModifiedDateTime") or start_value, now),
                "url": event.get("webLink"), "payload": payload,
            })
            series_id = event.get("seriesMasterId")
            if series_id and series_id not in series_seen:
                series_seen.add(series_id)
                imported.append({
                    "type": "series", "id": str(series_id), "canonical": "Meeting Series",
                    "title": str(event.get("subject") or "Recurring meeting"),
                    "version": str(event.get("lastModifiedDateTime") or "1"),
                    "updated": parse_time(event.get("lastModifiedDateTime"), now),
                    "url": event.get("webLink"), "payload": {"calendar_id": calendar_id},
                })

        created = updated = unchanged = 0
        for item in imported:
            encoded = json.dumps(item["payload"], sort_keys=True, separators=(",", ":"), default=str)
            fingerprint = sha256(encoded.encode()).hexdigest()
            record = db.query(IntegrationSourceRecord).filter_by(
                tenant_id=row.tenant_id, provider_tenant_id=account_id,
                external_entity_type=item["type"], external_entity_id=item["id"],
            ).first()
            if not record:
                record = IntegrationSourceRecord(
                    connection_id=row.id, tenant_id=row.tenant_id, provider="microsoft",
                    provider_tenant_id=account_id, external_entity_type=item["type"],
                    external_entity_id=item["id"], canonical_entity_type=item["canonical"],
                    canonical_entity_id=item["id"], first_synchronized_at=now,
                    source_version=item["version"], source_updated_at=item["updated"],
                    content_fingerprint=fingerprint, title=item["title"], source_url=item["url"],
                    classification="INTERNAL", data_status="CURRENT", safe_payload=item["payload"],
                )
                db.add(record)
                created += 1
            elif record.content_fingerprint != fingerprint or record.source_version != item["version"]:
                record.source_version=item["version"]; record.source_updated_at=item["updated"]
                record.content_fingerprint=fingerprint; record.title=item["title"]
                record.source_url=item["url"]; record.safe_payload=item["payload"]
                updated += 1
            else:
                unchanged += 1
            record.last_synchronized_at = now
            record.last_successful_run_id = run.id

        cursor = f"outlook:{now.isoformat()}"
        run.status="SUCCEEDED"; run.ended_at=now; run.cursor_end=cursor
        run.counters={"discovered":len(imported),"created":created,"updated":updated,"unchanged":unchanged,"skipped":0,"quarantined":0,"failed":0}
        row.configuration={**(row.configuration or {}),"simulator":False,"sync_cursor":cursor,"source_scope":{"selection":"All calendars authorized for Ahmed Sabry"},"sync_policy":{"mode":"INCREMENTAL","window_past_days":30,"window_future_days":90,"bounded_record_limit":1000}}
        row.safe_metadata={**(row.safe_metadata or {}),"mode":"LIVE","calendar_count":len(calendars),"event_count":len(events),"last_sync_run_id":run.id}
        row.status="CONNECTED"; row.health_status="healthy"; row.enabled=True
        row.last_error_code=row.last_error_message_safe=None
        db.commit()
        print(f"Live Outlook synchronization succeeded: {len(calendars)} calendars and {len(events)} events read.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
