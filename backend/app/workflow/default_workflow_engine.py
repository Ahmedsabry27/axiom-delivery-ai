from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.agents.registry import AgentRegistry
from app.contracts.results import (
    AgentResult,
    WorkflowResult,
)
from app.contracts.workflow_engine import WorkflowEngine
from app.contracts.workflow_repository import WorkflowRepository
from app.events.runtime_events import (
    TaskRetrying,
    TaskTimedOut,
)
from app.logging.logger import logger
from app.runtime.approval_coordinator import (
    ApprovalCancelledError,
    ApprovalCoordinator,
    ApprovalRejectedError,
)
from app.runtime.cancellation_token import (
    CancellationToken,
    WorkflowCancelledError,
)
from app.runtime.checkpoint_manager import CheckpointManager
from app.runtime.context import RuntimeContext
from app.runtime.event_bus import EventBus
from app.runtime.parallel_executor import ParallelExecutor
from app.runtime.task import Task
from app.runtime.task_graph import TaskGraph
from app.runtime.task_state import TaskState
from app.runtime.workflow import Workflow
from app.runtime.workflow_state_manager import WorkflowStateManager


class DefaultWorkflowEngine(WorkflowEngine):
    """
    Enterprise workflow engine.

    Responsibilities
    ----------------
    • Execute dependency-aware workflows
    • Execute tasks in parallel
    • Execute registered agents
    • Handle retries
    • Handle task timeouts
    • Handle pause / resume
    • Handle workflow cancellation
    • Coordinate human approvals
    • Persist checkpoints
    • Publish runtime events
    • Aggregate workflow results

    Workflow lifecycle is delegated to WorkflowStateManager.

    Human approvals are coordinated through ApprovalCoordinator.

    Checkpoint persistence is delegated to CheckpointManager.
    """

    EVENT_SOURCE = "DefaultWorkflowEngine"

    def __init__(
        self,
        agent_registry: AgentRegistry,
        event_bus: EventBus,
        repository: WorkflowRepository,
        parallel_executor: ParallelExecutor | None = None,
        state_manager: WorkflowStateManager | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        cancellation_token: CancellationToken | None = None,
        approval_coordinator: ApprovalCoordinator | None = None,
    ) -> None:
        """
        Initialize the workflow engine.

        Every dependency is injectable to support
        unit testing and custom enterprise implementations.
        """

        self._agent_registry = agent_registry
        self._event_bus = event_bus
        self._repository = repository

        self._parallel_executor = (
            parallel_executor if parallel_executor is not None else ParallelExecutor()
        )

        self._state_manager = (
            state_manager
            if state_manager is not None
            else WorkflowStateManager(
                repository=repository,
                event_bus=event_bus,
            )
        )

        self._checkpoint_manager = (
            checkpoint_manager
            if checkpoint_manager is not None
            else CheckpointManager(
                repository=repository,
            )
        )

        self._cancellation_token = (
            cancellation_token
            if cancellation_token is not None
            else CancellationToken()
        )

        self._approval_coordinator = (
            approval_coordinator
            if approval_coordinator is not None
            else ApprovalCoordinator()
        )

    async def execute(
        self,
        workflow: Workflow,
        context: RuntimeContext,
    ) -> WorkflowResult:
        """
        Execute a workflow using dependency-aware scheduling.

        Responsibilities
        ----------------
        • Start workflow lifecycle
        • Execute dependency graph
        • Coordinate task execution
        • Persist checkpoints
        • Complete workflow lifecycle
        • Aggregate execution results
        """

        logger.info(
            "Starting workflow '%s' (%s).",
            workflow.goal,
            workflow.id,
        )

        await self._wait_if_paused_or_cancelled()

        await self._state_manager.start_workflow(
            workflow,
        )

        try:
            graph = TaskGraph(
                workflow.tasks,
            )

            logger.debug(
                "Workflow '%s' contains %d task(s).",
                workflow.goal,
                len(workflow.tasks),
            )

            task_results = await self._parallel_executor.execute(
                graph=graph,
                execute_task=lambda task: self._execute_task(
                    workflow=workflow,
                    task=task,
                    context=context,
                ),
            )

            await self._wait_if_paused_or_cancelled()

            await self._checkpoint_manager.save_checkpoint(
                workflow,
            )

            self._assert_required_tasks_succeeded(workflow, graph)

            await self._state_manager.complete_workflow(
                workflow,
            )

            logger.info(
                "Workflow '%s' completed successfully.",
                workflow.goal,
            )

            return WorkflowResult(
                success=True,
                output={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "started_at": (
                        workflow.started_at.isoformat() if workflow.started_at else None
                    ),
                    "completed_at": (
                        workflow.completed_at.isoformat()
                        if workflow.completed_at
                        else None
                    ),
                    "duration_ms": self._workflow_duration_ms(
                        workflow,
                    ),
                    "tasks_total": len(workflow.tasks),
                    # Number of tasks actually executed by the executor
                    "tasks_executed": len(task_results),
                    "tasks_completed": self._count_completed_tasks(
                        workflow,
                    ),
                    "tasks_failed": self._count_failed_tasks(
                        workflow,
                    ),
                    "results": task_results,
                },
            )

        except WorkflowCancelledError:
            logger.warning(
                "Workflow '%s' was cancelled.",
                workflow.goal,
            )

            await self._state_manager.cancel_workflow(
                workflow,
            )

            await self._checkpoint_manager.save_checkpoint(
                workflow,
            )

            raise

        except Exception as ex:
            logger.exception(
                "Workflow '%s' failed.",
                workflow.goal,
            )

            await self._state_manager.fail_workflow(
                workflow,
                error=str(ex),
            )

            await self._checkpoint_manager.save_checkpoint(
                workflow,
            )

            raise

    @staticmethod
    def _task_is_required(task: Task) -> bool:
        """Tasks are required unless plan metadata explicitly marks them optional."""
        return bool((task.metadata or {}).get("required", True))

    @classmethod
    def _assert_required_tasks_succeeded(
        cls, workflow: Workflow, graph: TaskGraph
    ) -> None:
        failed = [
            task.name
            for task in workflow.tasks
            if cls._task_is_required(task)
            and (
                task.state
                in {
                    TaskState.FAILED,
                    TaskState.TIMED_OUT,
                    TaskState.CANCELLED,
                }
                or task.id in graph.failed_tasks
                or task.id in graph.blocked_tasks
            )
        ]
        incomplete = [
            task.name
            for task in workflow.tasks
            if cls._task_is_required(task)
            and task.state != TaskState.COMPLETED
            and task.name not in failed
        ]
        if failed or incomplete:
            details = ", ".join([*failed, *incomplete])
            raise RuntimeError(
                f"Required workflow tasks did not complete successfully: {details}"
            )

    async def _execute_task(
        self,
        workflow: Workflow,
        task: Task,
        context: RuntimeContext,
    ) -> dict[str, Any]:
        """
        Execute a single workflow task.

        Responsibilities
        ----------------
        • Validate pause/cancellation
        • Request human approval when required
        • Execute the assigned agent
        • Handle retries
        • Handle task timeouts
        • Persist checkpoints
        • Aggregate execution results
        """

        logger.info(
            "Executing task '%s'.",
            task.name,
        )

        await self._wait_if_paused_or_cancelled()

        task.last_error = None
        task.attempt = 1

        await self._state_manager.start_task(
            workflow,
            task,
        )

        max_attempts = task.retry_count + 1

        while task.attempt <= max_attempts:
            try:
                #
                # Respect workflow pause/cancellation
                #
                await self._wait_if_paused_or_cancelled()

                logger.debug(
                    "Task '%s' - Attempt %d/%d",
                    task.name,
                    task.attempt,
                    max_attempts,
                )

                #
                # ----------------------------------------------------------
                # Human approval checkpoint
                # ----------------------------------------------------------
                #
                if task.requires_approval:
                    logger.info(
                        "Task '%s' requires approval.",
                        task.name,
                    )

                    approval = await self._approval_coordinator.create(
                        workflow_id=str(workflow.id),
                        task_id=str(task.id),
                        title=(task.approval_title or task.name),
                        description=(task.approval_description or task.description),
                        requested_by=(task.approval_requested_by or self.EVENT_SOURCE),
                        assigned_to=(task.approval_assigned_to or ""),
                    )

                    await self._state_manager.approval_pending(
                        workflow,
                    )

                    logger.info(
                        "Waiting for approval '%s'.",
                        approval.id,
                    )

                    await self._approval_coordinator.wait_for_approval(
                        approval.id,
                        timeout_seconds=task.approval_timeout_seconds,
                    )

                    logger.info(
                        "Approval '%s' granted.",
                        approval.id,
                    )

                    await self._state_manager.resume_workflow(
                        workflow,
                    )

                #
                # ----------------------------------------------------------
                # Execute assigned agent
                # ----------------------------------------------------------
                #

                await self._wait_if_paused_or_cancelled()
                result = await self._execute_agent(
                    task=task,
                    context=context,
                )

                await self._state_manager.complete_task(
                    workflow,
                    task,
                )

                await self._checkpoint_manager.save_checkpoint(
                    workflow,
                )

                logger.info(
                    "Task '%s' completed successfully.",
                    task.name,
                )

                return self._build_task_result(
                    task=task,
                    result=result,
                )

            except ApprovalRejectedError as ex:
                task.last_error = str(ex)

                logger.warning(
                    "Approval rejected for task '%s'.",
                    task.name,
                )

                await self._state_manager.fail_task(
                    workflow=workflow,
                    task=task,
                    error=task.last_error,
                )

                await self._checkpoint_manager.save_checkpoint(
                    workflow,
                )

                raise

            except ApprovalCancelledError as ex:
                task.last_error = str(ex)

                logger.warning(
                    "Approval cancelled for task '%s'.",
                    task.name,
                )

                await self._state_manager.fail_task(
                    workflow=workflow,
                    task=task,
                    error=task.last_error,
                    state=TaskState.CANCELLED,
                )

                await self._checkpoint_manager.save_checkpoint(
                    workflow,
                )

                raise

            except asyncio.TimeoutError as ex:
                task.last_error = str(ex)

                logger.warning(
                    "Task '%s' timed out on attempt %d/%d.",
                    task.name,
                    task.attempt,
                    max_attempts,
                )

                if task.attempt < max_attempts:
                    await self._event_bus.publish(
                        TaskRetrying(
                            workflow_id=str(workflow.id),
                            task_id=str(task.id),
                            task_name=task.name,
                            attempt=task.attempt,
                            max_attempts=max_attempts,
                            reason="timeout",
                            source=self.EVENT_SOURCE,
                            timestamp=datetime.now(UTC),
                        )
                    )

                    task.attempt += 1

                    await self._checkpoint_manager.save_checkpoint(
                        workflow,
                    )

                    continue

                await self._state_manager.fail_task(
                    workflow=workflow,
                    task=task,
                    error=task.last_error,
                    state=TaskState.TIMED_OUT,
                )

                await self._event_bus.publish(
                    TaskTimedOut(
                        workflow_id=str(workflow.id),
                        task_id=str(task.id),
                        task_name=task.name,
                        timeout_seconds=task.timeout_seconds,
                        source=self.EVENT_SOURCE,
                        timestamp=datetime.now(UTC),
                    )
                )

                await self._checkpoint_manager.save_checkpoint(
                    workflow,
                )

                raise
            except Exception as ex:
                task.last_error = str(ex)

                logger.exception(
                    "Task '%s' failed on attempt %d/%d.",
                    task.name,
                    task.attempt,
                    max_attempts,
                )

                if task.attempt < max_attempts:
                    await self._event_bus.publish(
                        TaskRetrying(
                            workflow_id=str(workflow.id),
                            task_id=str(task.id),
                            task_name=task.name,
                            attempt=task.attempt,
                            max_attempts=max_attempts,
                            reason=str(ex),
                            source=self.EVENT_SOURCE,
                            timestamp=datetime.now(UTC),
                        )
                    )

                    task.attempt += 1

                    await self._checkpoint_manager.save_checkpoint(
                        workflow,
                    )

                    await self._wait_if_paused_or_cancelled()

                    continue

                await self._state_manager.fail_task(
                    workflow=workflow,
                    task=task,
                    error=task.last_error,
                )

                await self._checkpoint_manager.save_checkpoint(
                    workflow,
                )

                raise

        raise RuntimeError(f"Task '{task.name}' exited retry loop unexpectedly.")

    async def _execute_agent(
        self,
        task: Task,
        context: RuntimeContext,
    ) -> AgentResult:
        """
        Execute the agent assigned to a workflow task.

        Supports:
        - Explicit agent routing
        - Dynamic capability-based routing

        Retry handling, task state transitions and
        checkpointing are handled by _execute_task().
        """

        await self._wait_if_paused_or_cancelled()

        # ----------------------------------------------------------
        # Resolve Agent
        # ----------------------------------------------------------

        agent = None

        #
        # Case 1:
        # Explicit agent assignment
        #
        if task.agent:
            logger.debug(
                "Resolving explicit agent '%s' for task '%s'.",
                task.agent,
                task.name,
            )

            agent = self._agent_registry.get(task.agent)

        #
        # Case 2:
        # Dynamic capability based routing
        #
        elif task.required_capabilities:
            logger.debug(
                "Selecting agent dynamically for task '%s'. Required capabilities=%s",
                task.name,
                task.required_capabilities,
            )

            if task.required_capabilities and len(task.required_capabilities) > 0:
                agent = self._agent_registry.select_agent(task.required_capabilities)
            else:
                agent = self._agent_registry.get(task.agent)

            #
            # Store routing decision
            #
            task.metadata.update(
                {
                    "selected_agent": agent.name,
                    "routing_type": "dynamic",
                    "required_capabilities": (task.required_capabilities),
                }
            )

        #
        # Case 3:
        # No routing information
        #
        else:
            raise ValueError(
                f"Task '{task.name}' does not define an agent or required capabilities."
            )

        if agent is None:
            raise ValueError(f"No suitable agent found for task '{task.name}'.")

        logger.debug(
            "Executing agent '%s' for task '%s'.",
            agent.name,
            task.name,
        )

        result = await asyncio.wait_for(
            agent.execute(
                context=context,
                task=task,
            ),
            timeout=task.timeout_seconds,
        )

        await self._wait_if_paused_or_cancelled()

        if not isinstance(
            result,
            AgentResult,
        ):
            raise TypeError(
                f"Agent '{agent.name}' returned "
                f"{type(result).__name__}; "
                "expected AgentResult."
            )

        logger.debug(
            "Agent '%s' completed successfully.",
            agent.name,
        )

        return result
        """
        Execute the agent assigned to a workflow task.

        Responsibilities
        ----------------
        • Validate pause/cancellation
        • Resolve agent from registry
        • Execute agent
        • Enforce timeout
        • Validate returned result

        Retry handling, task state transitions and
        checkpointing are handled by _execute_task().
        """

        await self._wait_if_paused_or_cancelled()

        logger.debug(
            "Resolving agent '%s' for task '%s'.",
            task.agent,
            task.name,
        )

        agent = self._agent_registry.get(
            task.agent,
        )

        if agent is None:
            raise ValueError(f"Agent '{task.agent}' is not registered.")

        logger.debug(
            "Executing agent '%s' for task '%s'.",
            task.agent,
            task.name,
        )

        result = await asyncio.wait_for(
            agent.execute(
                context=context,
                task=task,
            ),
            timeout=task.timeout_seconds,
        )

        await self._wait_if_paused_or_cancelled()

        if not isinstance(
            result,
            AgentResult,
        ):
            raise TypeError(
                f"Agent '{task.agent}' returned "
                f"{type(result).__name__}; "
                "expected AgentResult."
            )

        logger.debug(
            "Agent '%s' completed successfully.",
            task.agent,
        )

        return result

    def _build_task_result(
        self,
        task: Task,
        result: AgentResult,
    ) -> dict[str, Any]:
        """
        Build a standardized task execution result.

        Converts the internal AgentResult into a
        serializable structure returned as part of
        the final WorkflowResult.

        Includes execution metrics, retry information,
        approval details and agent output.
        """

        approval_metadata = None

        if task.requires_approval:
            approval_metadata = {
                "required": True,
                "title": task.approval_title,
                "description": task.approval_description,
                "requested_by": task.approval_requested_by,
                "assigned_to": task.approval_assigned_to,
            }
        else:
            approval_metadata = {
                "required": False,
            }

        return {
            # ----------------------------------------------------------
            # Task Identity
            # ----------------------------------------------------------
            "task_id": str(task.id),
            "task": task.name,
            "task_name": task.name,
            "description": task.description,
            "agent": (task.metadata.get("selected_agent") or task.agent),
            "tool": task.tool,
            # ----------------------------------------------------------
            # Agent Routing
            # ----------------------------------------------------------
            "routing": {
                "type": (
                    task.metadata.get(
                        "routing_type",
                        "explicit",
                    )
                ),
                "required_capabilities": (task.required_capabilities),
                "selected_agent": (task.metadata.get("selected_agent")),
            },
            # ----------------------------------------------------------
            # Execution State
            # ----------------------------------------------------------
            "state": task.state.value,
            "attempt": task.attempt,
            "retry_count": task.retry_count,
            # ----------------------------------------------------------
            # Timing Metrics
            # ----------------------------------------------------------
            "started_at": (task.started_at.isoformat() if task.started_at else None),
            "completed_at": (
                task.completed_at.isoformat() if task.completed_at else None
            ),
            "duration_ms": task.duration_ms,
            # ----------------------------------------------------------
            # Approval Information
            # ----------------------------------------------------------
            "approval": approval_metadata,
            # ----------------------------------------------------------
            # Result
            # ----------------------------------------------------------
            "success": result.success,
            "output": result.output,
            "metadata": result.metadata,
            # ----------------------------------------------------------
            # Error Information
            # ----------------------------------------------------------
            "error": task.last_error,
        }

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    async def _wait_if_paused_or_cancelled(
        self,
    ) -> None:
        """
        Block execution while workflow is paused.

        Raises
        ------
        WorkflowCancelledError
            When cancellation has been requested.
        """

        await self._cancellation_token.wait_if_paused()

        await self._cancellation_token.throw_if_cancelled()

    @staticmethod
    def _count_completed_tasks(
        workflow: Workflow,
    ) -> int:
        """
        Return the number of successfully completed tasks.
        """

        return sum(task.state == TaskState.COMPLETED for task in workflow.tasks)

    @staticmethod
    def _count_failed_tasks(
        workflow: Workflow,
    ) -> int:
        """
        Return the number of failed tasks.

        Includes:
        - FAILED
        - TIMED_OUT
        - CANCELLED
        """

        return sum(
            task.state
            in {
                TaskState.FAILED,
                TaskState.TIMED_OUT,
                TaskState.CANCELLED,
            }
            for task in workflow.tasks
        )

    @staticmethod
    def _workflow_duration_ms(
        workflow: Workflow,
    ) -> float | None:
        """
        Calculate workflow execution duration.

        Returns
        -------
        float | None
            Duration in milliseconds.
        """

        if workflow.started_at is None or workflow.completed_at is None:
            return None

        return round(
            (workflow.completed_at - workflow.started_at).total_seconds() * 1000,
            2,
        )

    @staticmethod
    def _is_workflow_completed(
        workflow: Workflow,
    ) -> bool:
        """
        Determine whether workflow reached
        a terminal state.
        """

        return workflow.state.value in {
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }

    @staticmethod
    def _has_failed_tasks(
        workflow: Workflow,
    ) -> bool:
        """
        Determine whether workflow contains
        failed tasks.
        """

        return any(
            task.state
            in {
                TaskState.FAILED,
                TaskState.TIMED_OUT,
                TaskState.CANCELLED,
            }
            for task in workflow.tasks
        )
