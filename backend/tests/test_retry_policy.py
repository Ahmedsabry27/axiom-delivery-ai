import pytest


@pytest.mark.asyncio
async def test_retry_execution():

    attempts = 0

    async def execute_with_retry(max_attempts: int):

        nonlocal attempts

        while attempts < max_attempts:
            attempts += 1

            try:
                if attempts < 3:
                    raise Exception("failed")

                return True

            except Exception:
                if attempts == max_attempts:
                    raise

    result = await execute_with_retry(3)

    assert attempts == 3
    assert result is True
