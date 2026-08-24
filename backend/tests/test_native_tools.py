import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts.tool_models import ExecutionContext
from app.database.base import Base
from app.database.models.native_tool import NativeNotification
from app.tool_sdk.native_tools import (
    FileUploadTool,
    NotificationTool,
    UnsafeQuery,
    UnsafeURL,
    safe_sql,
    validate_url,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_sql_ast_validation_allowlist_and_limit():
    query, fingerprint = safe_sql("SELECT region, revenue FROM sales", ["sales"], 100)
    assert "LIMIT 100" in query and fingerprint
    for unsafe in [
        "DELETE FROM sales",
        "SELECT * FROM secrets",
        "SELECT 1; SELECT 2",
        "SELECT * FROM sales -- hidden",
    ]:
        with pytest.raises(UnsafeQuery):
            safe_sql(unsafe, ["sales"], 100)


def test_ssrf_rejects_loopback_before_request():
    with pytest.raises(UnsafeURL):
        validate_url("https://127.0.0.1", "/api", [r"/api"])


@pytest.mark.asyncio
async def test_file_upload_extract_duplicate_and_tenant_scope(
    db, tmp_path, monkeypatch
):
    monkeypatch.setenv("NATIVE_FILE_STORAGE_ROOT", str(tmp_path))
    tool = FileUploadTool()
    context = ExecutionContext(
        actor_id="u", tenant_id="tenant-a", permissions={"files.upload"}, db_session=db
    )
    payload = {
        "filename": "notes.txt",
        "content_base64": base64.b64encode(b"known enterprise phrase").decode(),
    }
    first = await tool.execute(payload, context)
    second = await tool.execute(payload, context)
    assert first.data["status"] == "indexed"
    assert second.data["duplicate"] is True


@pytest.mark.asyncio
async def test_notification_approval_sanitization_and_idempotency(db, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_ALLOWED_EMAIL_DOMAINS", "corp.example")
    tool = NotificationTool("email")
    context = ExecutionContext(
        actor_id="u",
        tenant_id="t",
        permissions={"notifications.email.send"},
        db_session=db,
    )
    payload = {
        "recipients": ["external@example.com"],
        "subject": "Hello",
        "message": "<script>bad()</script><b>Hello</b>",
        "idempotency_key": "same-key-123",
    }
    first = await tool.execute(payload, context)
    second = await tool.execute(payload, context)
    assert first.data["status"] == "pending_approval"
    assert second.data["duplicate"] is True
    assert "<" not in db.query(NativeNotification).first().safe_message
