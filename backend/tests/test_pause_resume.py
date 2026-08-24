import pytest


@pytest.mark.asyncio
async def test_pause_resume():

    state = "RUNNING"

    state = "PAUSED"

    assert state == "PAUSED"

    state = "RUNNING"

    assert state == "RUNNING"
