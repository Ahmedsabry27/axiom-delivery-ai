import asyncio

import pytest


@pytest.mark.asyncio
async def test_parallel_tasks():

    completed = []

    async def task(name):

        await asyncio.sleep(0.1)

        completed.append(name)

    await asyncio.gather(
        task("A"),
        task("B"),
        task("C"),
    )

    assert completed == [
        "A",
        "B",
        "C",
    ]
