from __future__ import annotations

from backend.app.runtime.approval_coordinator import ApprovalManager

from app.contracts.workflow_engine import WorkflowEngine
from app.contracts.workflow_repository import WorkflowRepository
from app.runtime.cancellation_token import CancellationToken
from app.runtime.checkpoint_manager import CheckpointManager
from app.runtime.context import RuntimeContext
from app.runtime.workflow import Workflow
from app.runtime.workflow_state_manager import WorkflowStateManager


class WorkflowController:
    """
    High-level orchestration service for workflow execution.

    Responsibilities:

    - Start workflows
    - Resume workflows
    - Cancel workflows
    - Save checkpoints
    - Restore checkpoints
    - Manage approvals

    Workflow execution itself is delegated to WorkflowEngine.
    """

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        repository: WorkflowRepository,
        state_manager: WorkflowStateManager,
        checkpoint_manager: CheckpointManager,
        approval_manager: ApprovalManager,
    ) -> None:

        self._engine = workflow_engine
        self._repository = repository
        self._state_manager = state_manager
        self._checkpoint_manager = checkpoint_manager
        self._approval_manager = approval_manager

        self._tokens: dict[str, CancellationToken] = {}

    async def start(
        self,
        workflow: Workflow,
        context: RuntimeContext,
    ) -> dict:

        token = CancellationToken()

        self._tokens[str(workflow.id)] = token

        context.cancellation_token = token

        return await self._engine.execute(
            workflow,
            context,
        )

    async def resume(
        self,
        workflow_id: str,
        context: RuntimeContext,
    ) -> dict:

        workflow = await self._checkpoint_manager.restore(
            workflow_id,
        )

        if workflow is None:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        token = CancellationToken()

        self._tokens[workflow_id] = token

        context.cancellation_token = token

        return await self._engine.execute(
            workflow,
            context,
        )

    async def cancel(
        self,
        workflow_id: str,
    ) -> None:

        token = self._tokens.get(workflow_id)

        if token is None:
            return

        token.cancel()

    async def checkpoint(
        self,
        workflow_id: str,
    ) -> None:

        workflow = await self._repository.get(
            workflow_id,
        )

        if workflow is None:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        await self._checkpoint_manager.save_checkpoint(
            workflow,
        )

    async def approve(
        self,
        approval_id: str,
        comments: str | None = None,
    ):

        return await self._approval_manager.approve(
            approval_id,
            comments,
        )

    async def reject(
        self,
        approval_id: str,
        comments: str | None = None,
    ):

        return await self._approval_manager.reject(
            approval_id,
            comments,
        )

    async def pending_approvals(self):

        return await self._approval_manager.pending()
