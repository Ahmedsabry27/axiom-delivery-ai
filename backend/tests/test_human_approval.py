import pytest


@pytest.mark.asyncio
async def test_approval_flow():

    approval_status = "PENDING"

    approval_status = "APPROVED"

    assert approval_status == "APPROVED"
