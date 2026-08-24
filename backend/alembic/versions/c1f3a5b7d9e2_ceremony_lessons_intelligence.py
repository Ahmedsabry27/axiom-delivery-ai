"""Add ceremony and lessons intelligence.

Revision ID: c1f3a5b7d9e2
Revises: b8d0f2a4c6e9
"""

from collections.abc import Sequence

from alembic import op
from app.database.models.ceremony import (
    Ceremony,
    CeremonyChecklistResponse,
    CeremonyTemplate,
    Lesson,
    LessonAdoption,
)

revision = "c1f3a5b7d9e2"
down_revision: str | Sequence[str] | None = "b8d0f2a4c6e9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (
        CeremonyTemplate.__table__,
        Ceremony.__table__,
        CeremonyChecklistResponse.__table__,
        Lesson.__table__,
        LessonAdoption.__table__,
    ):
        table.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for table in (
        LessonAdoption.__table__,
        Lesson.__table__,
        CeremonyChecklistResponse.__table__,
        Ceremony.__table__,
        CeremonyTemplate.__table__,
    ):
        table.drop(bind, checkfirst=True)
