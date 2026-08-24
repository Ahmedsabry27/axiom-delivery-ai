"""Synchronize real calendar-backed Teams meetings for a Microsoft account."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.database.models.integration import (
    IntegrationConnection,
    IntegrationSourceRecord,
    IntegrationSyncRun,
    ProviderAuthorization,
)
from app.database.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        outlook = db.query(IntegrationConnection).filter_by(
            tenant_id="axiom-demo", connector_type="outlook_calendar"
        ).one()
        row = db.query(IntegrationConnection).filter_by(
            tenant_id="axiom-demo", connector_type="microsoft_teams"
        ).one()
        account_id = (outlook.configuration or {}).get("provider_tenant_id")
        auth = db.query(ProviderAuthorization).filter_by(
            tenant_id=row.tenant_id,
            provider="microsoft",
            provider_tenant_id=account_id,
        ).one()
        events = db.query(IntegrationSourceRecord).filter_by(
            connection_id=outlook.id,
            tenant_id=row.tenant_id,
            provider_tenant_id=account_id,
            external_entity_type="event",
        ).all()
        teams_events = [
            event
            for event in events
            if event.safe_payload.get("is_online_meeting")
            and (
                "teams" in str(event.safe_payload.get("online_meeting_provider", "")).lower()
                or "teams.microsoft.com" in str(event.safe_payload.get("join_url", "")).lower()
            )
        ]
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
            correlation_ref=f"teams-live-{uuid4().hex[:16]}",
            started_at=now,
        )
        db.add(run)
        db.flush()
        created = updated = unchanged = 0
        for event in teams_events:
            payload = {
                "calendar_event_id": event.external_entity_id,
                "start": event.safe_payload.get("start"),
                "end": event.safe_payload.get("end"),
                "organizer": event.safe_payload.get("organizer"),
                "attendee_count": event.safe_payload.get("attendee_count"),
                "join_url": event.safe_payload.get("join_url"),
                "provider": event.safe_payload.get("online_meeting_provider"),
                "is_cancelled": event.safe_payload.get("is_cancelled"),
                "source": "Microsoft Graph calendar event",
            }
            fingerprint = sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            record = db.query(IntegrationSourceRecord).filter_by(
                tenant_id=row.tenant_id,
                provider_tenant_id=account_id,
                external_entity_type="meeting",
                external_entity_id=event.external_entity_id,
            ).first()
            if not record:
                record = IntegrationSourceRecord(
                    connection_id=row.id,
                    tenant_id=row.tenant_id,
                    provider="microsoft",
                    provider_tenant_id=account_id,
                    external_entity_type="meeting",
                    external_entity_id=event.external_entity_id,
                    canonical_entity_type="Meeting",
                    canonical_entity_id=event.external_entity_id,
                    source_version=event.source_version,
                    source_updated_at=event.source_updated_at,
                    content_fingerprint=fingerprint,
                    title=event.title,
                    source_url=event.safe_payload.get("join_url") or event.source_url,
                    classification="INTERNAL",
                    data_status="CURRENT",
                    safe_payload=payload,
                    first_synchronized_at=now,
                )
                db.add(record)
                created += 1
            elif record.content_fingerprint != fingerprint:
                record.source_version = event.source_version
                record.source_updated_at = event.source_updated_at
                record.content_fingerprint = fingerprint
                record.title = event.title
                record.source_url = event.safe_payload.get("join_url") or event.source_url
                record.safe_payload = payload
                updated += 1
            else:
                unchanged += 1
            record.last_synchronized_at = now
            record.last_successful_run_id = run.id

        cursor = f"teams-calendar:{now.isoformat()}"
        run.status = "SUCCEEDED"
        run.ended_at = now
        run.cursor_end = cursor
        run.counters = {
            "discovered": len(teams_events),
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "skipped": 0,
            "quarantined": 0,
            "failed": 0,
        }
        row.secret_ref = auth.secret_ref
        row.auth_type = "oauth2"
        row.display_name = f"{auth.account_label} Microsoft Teams"
        row.base_url = "https://graph.microsoft.com/v1.0"
        row.configuration = {
            **(row.configuration or {}),
            "simulator": False,
            "provider_tenant_id": account_id,
            "sync_cursor": cursor,
            "source_scope": {"selection": "Calendar-backed Microsoft Teams meetings"},
            "sync_policy": {
                "mode": "INCREMENTAL",
                "window_past_days": 30,
                "window_future_days": 90,
                "transcripts": "UNSUPPORTED_FOR_PERSONAL_ACCOUNT",
                "attendance": "UNSUPPORTED_FOR_PERSONAL_ACCOUNT",
            },
        }
        row.safe_metadata = {
            "mode": "LIVE",
            "account": auth.account_label,
            "meeting_count": len(teams_events),
            "source": "Microsoft Graph calendar events",
            "account_capability": "PERSONAL_ACCOUNT_CALENDAR_TEAMS_ONLY",
            "last_sync_run_id": run.id,
        }
        row.status = "CONNECTED"
        row.health_status = "healthy"
        row.enabled = True
        row.last_error_code = row.last_error_message_safe = None
        db.commit()
        print(f"Live Teams synchronization succeeded: {len(teams_events)} calendar-backed Teams meetings imported.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
