from __future__ import annotations

import asyncio


class WorkflowCancelledError(Exception):
    """
    Raised when workflow execution is cancelled.
    """


class CancellationToken:
    """
    Controls workflow cancellation
    and pause/resume behaviour.
    """

    def __init__(self) -> None:

        self._cancelled = False

        self._pause_event = asyncio.Event()

        # Initially execution is allowed
        self._pause_event.set()

    def cancel(self) -> None:
        """
        Cancel workflow execution.
        """

        self._cancelled = True

    def pause(self) -> None:
        """
        Pause workflow execution.
        """

        self._pause_event.clear()

    def resume(self) -> None:
        """
        Resume workflow execution.
        """

        self._pause_event.set()

    async def wait_if_paused(self) -> None:
        """
        Wait until workflow is resumed.
        """

        await self._pause_event.wait()

    async def throw_if_cancelled(self) -> None:
        """
        Raise when cancellation requested.
        """

        if self._cancelled:
            raise WorkflowCancelledError("Workflow execution cancelled.")

    @property
    def is_cancelled(self) -> bool:

        return self._cancelled

    @property
    def is_paused(self) -> bool:

        return not self._pause_event.is_set()
