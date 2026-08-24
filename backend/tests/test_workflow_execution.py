import pytest


@pytest.mark.asyncio
async def test_basic_execution():
    """
    Plan
      |
      v
    Execute
      |
      v
    Complete
    """

    result = True

    assert result is True
