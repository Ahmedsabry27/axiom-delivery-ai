from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.agents.models.agent import (
    AgentDefinition,
    AgentHealth,
    AgentStatus,
)
from app.agents.models.capability import (
    AgentCapability,
)
from app.agents.models.metadata import (
    AgentMetadata,
)
from app.contracts.agent import Agent
from app.contracts.results import AgentResult
from app.events.agent_events import (
    AgentExecutionCompleted,
    AgentExecutionFailed,
)
from app.runtime.context import RuntimeContext
from app.runtime.event_bus import EventBus
from app.runtime.task import Task


class DefaultAgent(Agent):
    """
    Default runtime agent.

    Lifecycle:

    CREATED
        |
    initialize()
        |
    READY
        |
    execute()
        |
    shutdown()


    Capabilities:

    - task-execution

    Acts as fallback executor.
    Specialized agents should own domain capabilities.
    """

    name = "default-agent"

    def __init__(
        self,
        event_bus: EventBus | None = None,
    ) -> None:

        self._event_bus = event_bus if event_bus is not None else EventBus()

        self.definition = AgentDefinition(
            metadata=AgentMetadata(
                name=self.name,
                description=("Default enterprise runtime agent"),
            ),
            capabilities=[
                AgentCapability(
                    name="task-execution",
                    description=("Execute general workflow tasks"),
                    category="runtime",
                    supported_tasks=[
                        "execute_task",
                        "generic_task",
                    ],
                    metadata={
                        "priority": "standard",
                    },
                ),
            ],
        )

    async def initialize(
        self,
    ) -> None:
        """
        Initialize agent resources.
        """

        self.definition.status = AgentStatus.INITIALIZED

        self.definition.status = AgentStatus.READY

    async def execute(
        self,
        context: RuntimeContext,
        task: Task,
    ) -> AgentResult:
        """
        Execute assigned task.

        Tracks:
        - execution id
        - timestamps
        - duration
        - execution metrics

        Publishes:
        - AgentExecutionCompleted
        - AgentExecutionFailed
        """

        self.definition.status = AgentStatus.EXECUTING

        execution_id = uuid4()

        started_at = datetime.now(UTC)

        try:
            result = AgentResult(
                success=True,
                output={
                    "workflow_id": str(context.workflow_id),
                    "request_id": str(context.request_id),
                    "session_id": str(context.session_id),
                    "conversation_id": str(context.conversation_id),
                    "tenant_id": (context.tenant_id),
                    "user_id": (context.user_id),
                    "message": (f"Task '{task.name}' completed successfully."),
                    "goal": context.goal,
                    "task_id": str(task.id),
                    "task_name": task.name,
                },
                metadata={
                    "agent": self.name,
                    "task": task.name,
                },
                execution_metadata={
                    "execution_id": str(execution_id),
                    "agent": self.name,
                    "task": task.name,
                    "started_at": (started_at.isoformat()),
                },
            )

            completed_at = datetime.now(UTC)

            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            result.execution_metadata.update(
                {
                    "completed_at": (completed_at.isoformat()),
                    "duration_ms": duration_ms,
                    "status": "SUCCESS",
                }
            )

            self.definition.record_execution(
                success=True,
                duration_ms=duration_ms,
            )

            await self._event_bus.publish(
                AgentExecutionCompleted(
                    agent_name=self.name,
                    execution_id=str(execution_id),
                    task_name=task.name,
                    duration_ms=duration_ms,
                    timestamp=completed_at,
                    metadata={
                        "workflow_id": str(context.workflow_id),
                        "status": "SUCCESS",
                    },
                )
            )

            self.definition.status = AgentStatus.READY

            return result

        except Exception as ex:
            completed_at = datetime.now(UTC)

            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            self.definition.record_execution(
                success=False,
                duration_ms=duration_ms,
                error=str(ex),
            )

            self.definition.status = AgentStatus.FAILED

            await self._event_bus.publish(
                AgentExecutionFailed(
                    agent_name=self.name,
                    execution_id=str(execution_id),
                    task_name=task.name,
                    error=str(ex),
                    timestamp=completed_at,
                    metadata={
                        "workflow_id": str(context.workflow_id),
                        "status": "FAILED",
                    },
                )
            )

            raise

    async def health_check(
        self,
    ) -> AgentHealth:
        """
        Return current agent health.
        """

        return self.definition.health()

    async def shutdown(
        self,
    ) -> None:
        """
        Release agent resources.
        """

        self.definition.status = AgentStatus.STOPPED
