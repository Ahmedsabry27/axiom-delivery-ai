from __future__ import annotations

from abc import ABC, abstractmethod

from app.agents.models.agent import (
    AgentDefinition,
    AgentHealth,
)
from app.contracts.results import AgentResult
from app.runtime.context import RuntimeContext
from app.runtime.task import Task


class Agent(ABC):
    """
    Enterprise agent contract.

    Defines the lifecycle and execution
    responsibilities of all agents.

    Lifecycle:

        CREATED
          |
          v
        initialize()
          |
          v
        READY
          |
          v
        execute()
          |
          v
        shutdown()

    Responsibilities:
    - Resource initialization
    - Task execution
    - Health reporting
    - Resource cleanup
    """

    name: str

    definition: AgentDefinition | None = None

    @abstractmethod
    async def initialize(
        self,
    ) -> None:
        """
        Initialize agent resources.

        Examples:
        - Load models
        - Connect tools
        - Initialize clients
        - Prepare runtime dependencies
        """

    @abstractmethod
    async def execute(
        self,
        context: RuntimeContext,
        task: Task,
    ) -> AgentResult:
        """
        Execute an assigned workflow task.

        Parameters:
            context:
                Runtime execution context.

            task:
                Task assigned to the agent.
        """

    @abstractmethod
    async def health_check(
        self,
    ) -> AgentHealth:
        """
        Return current agent health.

        Used for:
        - Monitoring
        - Readiness checks
        - Operational dashboards
        """

    @abstractmethod
    async def shutdown(
        self,
    ) -> None:
        """
        Release agent resources.

        Examples:
        - Close connections
        - Release memory
        - Stop background workers
        """
