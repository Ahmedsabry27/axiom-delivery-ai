from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.workflow_engine import Workflow
from app.contracts.workflow_repository import WorkflowRepository
from app.events.runtime_events import (
    WorkflowRecovering,
)
from app.runtime.event_bus import EventBus


class CheckpointManager:
    """
    Manages workflow execution checkpoints.

    Responsibilities
    ----------------
    • Persist workflow execution snapshots
    • Restore workflows after interruption
    • Track checkpoint metadata
    • Support workflow recovery
    """

    EVENT_SOURCE = "CheckpointManager"

    def __init__(
        self,
        repository: WorkflowRepository,
        event_bus: EventBus | None = None,
    ) -> None:

        self._repository = repository
        self._event_bus = event_bus

    async def save_checkpoint(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Persist the current workflow execution state.
        """

        workflow.last_checkpoint_at = datetime.now(UTC)

        await self._repository.save(
            workflow,
        )

    async def load_checkpoint(
        self,
        workflow_id: str,
    ) -> Workflow | None:
        """
        Load the latest workflow checkpoint.
        """

        return await self._repository.get(
            workflow_id,
        )

    async def restore(
        self,
        workflow_id: str,
    ) -> Workflow | None:
        """
        Restore workflow from latest checkpoint.

        Used after:
        - application restart
        - worker failure
        - infrastructure interruption
        """

        workflow = await self.load_checkpoint(
            workflow_id,
        )

        if workflow is None:
            return None

        if self._event_bus:
            await self._event_bus.publish(
                WorkflowRecovering(
                    source=self.EVENT_SOURCE,
                    payload={
                        "workflow_id": str(workflow.id),
                        "state": workflow.state.value,
                        "checkpoint_time": (
                            workflow.last_checkpoint_at.isoformat()
                            if workflow.last_checkpoint_at
                            else None
                        ),
                        "restored_at": (datetime.now(UTC).isoformat()),
                    },
                )
            )

        return workflow

    async def delete_checkpoint(
        self,
        workflow_id: str,
    ) -> None:
        """
        Remove persisted checkpoint.

        Usually executed after successful completion
        when recovery is no longer required.
        """

        await self._repository.delete(
            workflow_id,
        )
