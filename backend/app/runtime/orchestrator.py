from __future__ import annotations

from app.contracts.planner import Planner
from app.contracts.results import WorkflowResult
from app.contracts.workflow_engine import WorkflowEngine
from app.events.runtime_events import (
    PlanningCompleted,
    PlanningFailed,
    PlanningStarted,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)
from app.logging.logger import logger
from app.runtime.context import RuntimeContext
from app.runtime.event_bus import EventBus
from app.runtime.workflow import Workflow


class RuntimeOrchestrator:
    """
    Coordinates the execution of a workflow.

    Responsibilities
    ----------------
    - Publish workflow lifecycle events
    - Invoke planner
    - Generate execution plan
    - Build workflow object
    - Delegate execution to WorkflowEngine

    Orchestration responsibilities only.
    Execution state management belongs to:
        WorkflowStateManager
        DefaultWorkflowEngine
    """

    EVENT_SOURCE = "RuntimeOrchestrator"

    def __init__(
        self,
        planner: Planner,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus,
    ) -> None:

        self._planner = planner

        self._workflow_engine = workflow_engine

        self._event_bus = event_bus

    async def run(
        self,
        context: RuntimeContext,
    ) -> WorkflowResult:
        """
          Execute a workflow lifecycle.

          Flow:

          RuntimeContext
                |
                v
            Planner
                |
                v
            Workflow
                |
                v
        DefaultWorkflowEngine
                |
                v
            WorkflowResult
        """

        logger.info(
            "Starting workflow '%s' (%s)",
            context.goal,
            context.workflow_id,
        )

        await self._event_bus.publish(
            WorkflowStarted(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(context.workflow_id),
                    "goal": context.goal,
                },
            )
        )

        try:
            # --------------------------------------------------
            # Step 1 - Create execution plan
            # --------------------------------------------------

            await self._event_bus.publish(
                PlanningStarted(
                    source=self.EVENT_SOURCE,
                    payload={"workflow_id": str(context.workflow_id)},
                )
            )
            plan = await self._planner.plan(context)
            await self._event_bus.publish(
                PlanningCompleted(
                    source=self.EVENT_SOURCE,
                    payload={
                        "workflow_id": str(context.workflow_id),
                        "tasks_total": len(plan.tasks),
                        "plan": {
                            "goal": plan.goal,
                            "estimated_duration_seconds": plan.estimated_duration_seconds,
                            "estimated_cost": plan.estimated_cost,
                            "steps": [
                                {
                                    "id": str(task.id),
                                    "name": task.name,
                                    "description": task.description,
                                    "type": "tool" if task.tool else "agent",
                                    "tool": task.tool,
                                    "agent": task.agent,
                                    "dependencies": [
                                        str(item) for item in task.depends_on
                                    ],
                                    "required_inputs": list(
                                        (task.metadata or {}).get("required_inputs", [])
                                    ),
                                    "status": "pending",
                                }
                                for task in plan.tasks
                            ],
                        },
                    },
                )
            )

            logger.info(
                "Execution plan created with %d task(s).",
                len(plan.tasks),
            )

            # --------------------------------------------------
            # Step 2 - Create workflow instance
            # --------------------------------------------------

            workflow = Workflow(
                id=context.workflow_id,
                goal=plan.goal,
                tasks=plan.tasks,
                metadata={
                    "request_id": str(context.request_id),
                    "session_id": str(context.session_id),
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                },
            )

            # --------------------------------------------------
            # Step 3 - Execute workflow
            # --------------------------------------------------

            result = await self._workflow_engine.execute(
                workflow=workflow,
                context=context,
            )

            # --------------------------------------------------
            # Step 4 - Publish completion event
            # --------------------------------------------------

            await self._event_bus.publish(
                WorkflowCompleted(
                    source=self.EVENT_SOURCE,
                    payload={
                        "workflow_id": str(workflow.id),
                        "goal": workflow.goal,
                        "state": workflow.state.value,
                    },
                )
            )

            logger.info(
                "Workflow '%s' completed successfully.",
                workflow.id,
            )

            return result

        except Exception as ex:
            logger.exception(
                "Workflow '%s' failed.",
                context.workflow_id,
            )

            await self._event_bus.publish(
                PlanningFailed(
                    source=self.EVENT_SOURCE,
                    payload={
                        "workflow_id": str(context.workflow_id),
                        "error": str(ex),
                    },
                )
            )

            await self._event_bus.publish(
                WorkflowFailed(
                    source=self.EVENT_SOURCE,
                    payload={
                        "workflow_id": str(context.workflow_id),
                        "goal": context.goal,
                        "error": str(ex),
                    },
                )
            )

            raise
