"""Add durable Meeting Intelligence.

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
"""

from collections.abc import Sequence

from alembic import op
from app.database.models.meeting import (
    FindingEvidence,
    Meeting,
    MeetingArtifact,
    MeetingFinding,
    MeetingParticipant,
    MeetingTranscript,
    TranscriptSegment,
)

revision: str = "b2d4f6a8c0e1"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        Meeting.__table__,
        MeetingParticipant.__table__,
        MeetingTranscript.__table__,
        TranscriptSegment.__table__,
        MeetingFinding.__table__,
        FindingEvidence.__table__,
        MeetingArtifact.__table__,
    ):
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        MeetingArtifact.__table__,
        FindingEvidence.__table__,
        MeetingFinding.__table__,
        TranscriptSegment.__table__,
        MeetingTranscript.__table__,
        MeetingParticipant.__table__,
        Meeting.__table__,
    ):
        table.drop(bind, checkfirst=True)
