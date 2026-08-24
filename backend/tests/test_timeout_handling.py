import asyncio

import pytest


@pytest.mark.asyncio
async def test_task_timeout():

    async def slow_task():

        await asyncio.sleep(5)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            slow_task(),
            timeout=0.1,
        )
