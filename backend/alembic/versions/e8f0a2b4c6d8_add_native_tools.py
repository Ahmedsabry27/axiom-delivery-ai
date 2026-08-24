"""add Sprint 12 native tools
Revision ID: e8f0a2b4c6d8
Revises: d7e9f1a3b5c7
"""

import sqlalchemy as sa

from alembic import op

revision = "e8f0a2b4c6d8"
down_revision = "d7e9f1a3b5c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "native_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("normalized_filename", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("extension", sa.String(20), nullable=False),
        sa.Column("byte_size", sa.Integer, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(160), nullable=False),
        sa.Column("scan_status", sa.String(30), nullable=False),
        sa.Column("processing_status", sa.String(30), nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("extractor_version", sa.String(30)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "checksum", name="uq_native_file_checksum"),
    )
    op.create_index(
        "ix_native_files_status",
        "native_files",
        ["tenant_id", "processing_status", "created_at"],
    )
    op.create_table(
        "native_file_contents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("section", sa.String(120)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("character_count", sa.Integer, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index(
        "ix_native_content_search",
        "native_file_contents",
        ["tenant_id", "file_id", "sequence"],
    )
    op.create_table(
        "native_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("engine", sa.String(40)),
        sa.Column("base_url", sa.String(500)),
        sa.Column("secret_reference", sa.String(500)),
        sa.Column("safe_config", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("health_status", sa.String(30), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "kind", "display_name", name="uq_native_connection"
        ),
    )
    op.create_index(
        "ix_native_connections", "native_connections", ["tenant_id", "kind", "enabled"]
    )
    op.create_table(
        "native_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("recipient_summary", sa.JSON, nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column("safe_message", sa.Text, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("approval_state", sa.String(30), nullable=False),
        sa.Column("provider_message_id", sa.String(160)),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "tenant_id",
            "channel",
            "idempotency_key",
            name="uq_native_notification_idempotency",
        ),
    )
    op.create_index(
        "ix_native_notifications",
        "native_notifications",
        ["tenant_id", "status", "created_at"],
    )


def downgrade():
    op.drop_table("native_notifications")
    op.drop_table("native_connections")
    op.drop_table("native_file_contents")
    op.drop_table("native_files")
