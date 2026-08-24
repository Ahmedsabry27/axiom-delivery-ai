from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.meeting import (
    FindingEvidence,
    Meeting,
    MeetingFinding,
    TranscriptSegment,
)
from app.main import app
from app.meeting_intelligence.service import MeetingService, TranscriptParserService


def identity(actor="meeting-user", tenant="tenant-a"):
    return AgentIdentity.from_claims(
        {
            "sub": actor,
            "custom:tenant_id": tenant,
            "permissions": [
                "meetings.read",
                "meetings.create",
                "meetings.analyse",
                "meetings.review",
                "meetings.propose",
                "actions.create",
            ],
        }
    )


def test_transcript_parsers_are_deterministic_and_ground_speakers():
    plain = TranscriptParserService.parse(
        "Ahmed: We decided to ship Friday.\nThe owner is unclear.", "TEXT"
    )
    assert [(item.speaker, item.text) for item in plain] == [
        ("Ahmed", "We decided to ship Friday."),
        ("Unknown speaker", "The owner is unclear."),
    ]
    vtt = TranscriptParserService.parse(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nSarah: I will escalate today.\n",
        "VTT",
    )
    srt = TranscriptParserService.parse(
        "1\n00:00:01,000 --> 00:00:03,000\nSarah: I will escalate today.\n",
        "SRT",
    )
    assert vtt == srt
    assert vtt[0].speaker == "Sarah"


def test_stable_segment_ids_are_scoped_to_the_meeting(db_session):
    service = MeetingService(db_session, identity())
    first = service.create({"title": "First copy"})
    second = service.create({"title": "Second copy"})
    first_transcript = service.add_transcript(
        first.id, {"source_type": "TEXT", "content": "Ahmed: Same authorized note"}
    )
    second_transcript = service.add_transcript(
        second.id, {"source_type": "TEXT", "content": "Ahmed: Same authorized note"}
    )
    first_segment = (
        db_session.query(TranscriptSegment)
        .filter_by(transcript_id=first_transcript.id)
        .one()
    )
    second_segment = (
        db_session.query(TranscriptSegment)
        .filter_by(transcript_id=second_transcript.id)
        .one()
    )
    assert first_segment.id != second_segment.id


def test_meeting_analysis_review_proposal_and_artifact_are_durable(db_session):
    service = MeetingService(db_session, identity())
    meeting = service.create(
        {
            "title": "Release readiness",
            "meeting_type": "STEERING_COMMITTEE",
            "participants": [{"display_name": "Ahmed", "role": "Chair"}],
        }
    )
    transcript = service.add_transcript(
        meeting.id,
        {
            "source_type": "TEXT",
            "content": (
                "Ahmed: We decided to proceed with the release.\n"
                "Sarah: I will publish the readiness pack Friday.\n"
                "Omar: Risk: supplier certification may delay launch.\n"
                "Lina: The launch depends on security approval."
            ),
        },
    )
    first_ids = [
        row.id
        for row in db_session.query(TranscriptSegment)
        .filter_by(transcript_id=transcript.id)
        .order_by(TranscriptSegment.sequence)
    ]
    duplicate = service.add_transcript(
        meeting.id, {"source_type": "TEXT", "content": transcript.content}
    )
    assert duplicate.id == transcript.id
    assert len(first_ids) == 4 == len(set(first_ids))

    analysed = service.analyse(meeting.id)
    assert analysed.status == "NEEDS_REVIEW"
    findings = service.findings(meeting.id)
    assert {item.finding_type for item in findings} == {
        "DECISION",
        "ACTION",
        "RISK",
        "DEPENDENCY",
    }
    assert db_session.query(FindingEvidence).count() == 4
    accepted = service.review(
        meeting.id,
        findings[0].id,
        "ACCEPTED",
        {"expected_version": 1},
    )
    proposed = service.create_proposal(meeting.id, accepted.id)
    assert proposed.review_status == "PROPOSED"
    assert proposed.proposal_id
    minutes = service.artifact(meeting.id, "MEETING_MINUTES", True)
    assert minutes.version == 1
    assert findings[0].title in minutes.content


def test_meeting_tenant_isolation_and_cross_meeting_merge_fail_closed(db_session):
    owner = MeetingService(db_session, identity())
    first = owner.create({"title": "First"})
    second = owner.create({"title": "Second"})
    owner.add_transcript(
        first.id, {"source_type": "TEXT", "content": "Risk: first risk"}
    )
    owner.add_transcript(
        second.id, {"source_type": "TEXT", "content": "Risk: second risk"}
    )
    owner.analyse(first.id)
    owner.analyse(second.id)
    first_finding = owner.findings(first.id)[0]
    second_finding = owner.findings(second.id)[0]

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as merge_error:
        owner.review(
            first.id,
            first_finding.id,
            "MERGED",
            {"expected_version": 1, "merged_into_id": second_finding.id},
        )
    assert merge_error.value.status_code == 422
    with pytest.raises(HTTPException) as tenant_error:
        MeetingService(db_session, identity("other", "tenant-b")).get(first.id)
    assert tenant_error.value.status_code == 404
    assert db_session.query(Meeting).count() == 2
    assert db_session.query(MeetingFinding).count() == 2


def test_meeting_api_authorization_review_state_and_archive(db_session):
    claims = {
        "sub": "meeting-user",
        "custom:tenant_id": "tenant-a",
        "permissions": [
            "meetings.read",
            "meetings.create",
            "meetings.analyse",
            "meetings.review",
            "meetings.propose",
            "actions.create",
        ],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: claims
    try:
        client = TestClient(app)
        meeting = client.post("/api/meetings", json={"title": "API review"})
        assert meeting.status_code == 201
        meeting_id = meeting.json()["id"]
        denied = client.post(
            f"/api/meetings/{meeting_id}/transcript",
            json={
                "content": "Omar: Risk: unsafe release",
                "authorized_to_process": False,
            },
        )
        assert denied.status_code == 422
        uploaded = client.post(
            f"/api/meetings/{meeting_id}/transcript",
            json={
                "content": "Omar: Risk: unsafe release",
                "authorized_to_process": True,
            },
        )
        assert uploaded.status_code == 201
        assert client.post(f"/api/meetings/{meeting_id}/analyse").status_code == 200
        finding = client.get(f"/api/meetings/{meeting_id}/findings").json()["items"][0]
        blocked = client.post(f"/api/meetings/{meeting_id}/complete-review")
        assert blocked.status_code == 409
        accepted = client.post(
            f"/api/meetings/{meeting_id}/findings/{finding['id']}/accept",
            json={"expected_version": finding["version"]},
        )
        assert accepted.status_code == 200
        completed = client.post(f"/api/meetings/{meeting_id}/complete-review")
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"
        archived = client.post(f"/api/meetings/{meeting_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["status"] == "ARCHIVED"
    finally:
        app.dependency_overrides.clear()
