import pytest

from app.runtime.cancellation_token import (
    CancellationToken,
    WorkflowCancelledError,
)


@pytest.mark.asyncio
async def test_workflow_cancellation():

    token = CancellationToken()

    token.cancel()

    with pytest.raises(WorkflowCancelledError):
        await token.throw_if_cancelled()
