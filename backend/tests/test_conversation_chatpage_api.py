from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.main import app


@pytest.mark.asyncio
async def test_chatpage_conversation_contract_is_owned_and_array_shaped():
    identity = {
        "sub": "conversation-owner",
        "custom:tenant_id": "tenant-a",
    }
    app.dependency_overrides[get_current_user] = lambda: identity
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            empty = await client.get("/conversations")
            assert empty.status_code == 200
            assert empty.json() == []

            created = await client.post(
                "/conversations", json={"title": "ChatPage conversation"}
            )
            assert created.status_code == 200
            conversation = created.json()
            assert conversation["tenant_id"] == "tenant-a"

            listed = await client.get("/conversations")
            assert listed.status_code == 200
            assert listed.json() == [conversation]

            detail = await client.get(f"/conversations/{conversation['id']}")
            messages = await client.get(f"/conversations/{conversation['id']}/messages")
            assert detail.status_code == 200
            assert detail.json() == conversation
            assert messages.status_code == 200
            assert messages.json() == []

            app.dependency_overrides[get_current_user] = lambda: {
                "sub": "different-owner",
                "custom:tenant_id": "tenant-a",
            }
            other_list = await client.get("/conversations")
            other_detail = await client.get(f"/conversations/{conversation['id']}")
            assert other_list.status_code == 200
            assert other_list.json() == []
            assert other_detail.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
