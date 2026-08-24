from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.agents.models.capability import AgentCapability
from app.agents.models.configuration import AgentConfiguration
from app.agents.models.metadata import AgentMetadata


class AgentStatus(str, Enum):
    """
    Agent operational lifecycle status.
    """

    CREATED = "CREATED"

    INITIALIZED = "INITIALIZED"

    READY = "READY"

    EXECUTING = "EXECUTING"

    FAILED = "FAILED"

    STOPPED = "STOPPED"


@dataclass
class AgentHealth:
    """
    Runtime health information.
    """

    healthy: bool

    status: str

    executions: int = 0

    successful_executions: int = 0

    failed_executions: int = 0

    average_duration_ms: float = 0.0

    last_execution_at: datetime | None = None

    last_error: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def success_rate(
        self,
    ) -> float:
        """
        Calculate execution success rate.
        """

        if self.executions == 0:
            return 0.0

        return round(
            (self.successful_executions / self.executions) * 100,
            2,
        )


@dataclass
class AgentDefinition:
    """
    Enterprise agent definition.

    Contains:
    - Identity
    - Capabilities
    - Configuration
    - Lifecycle status
    - Runtime metrics
    """

    metadata: AgentMetadata

    capabilities: list[AgentCapability] = field(default_factory=list)

    id: UUID = field(default_factory=uuid4)

    status: AgentStatus = AgentStatus.CREATED

    configuration: AgentConfiguration = field(default_factory=AgentConfiguration)

    # -----------------------------
    # Runtime Metrics
    # -----------------------------

    executions: int = 0

    successful_executions: int = 0

    failed_executions: int = 0

    total_duration_ms: float = 0.0

    last_duration_ms: float | None = None

    last_execution_at: datetime | None = None

    last_error: str | None = None

    def has_capability(
        self,
        capability_name: str,
    ) -> bool:
        """
        Check agent capability.
        """

        return any(
            capability.name == capability_name for capability in self.capabilities
        )

    def record_execution(
        self,
        success: bool,
        duration_ms: float = 0,
        error: str | None = None,
    ) -> None:
        """
        Record execution metrics.
        """

        self.executions += 1

        self.last_execution_at = datetime.now(UTC)

        self.last_duration_ms = duration_ms

        self.total_duration_ms += duration_ms

        if success:
            self.successful_executions += 1

        else:
            self.failed_executions += 1

            self.last_error = error

    def success_rate(
        self,
    ) -> float:
        """
        Calculate execution success percentage.
        """

        if self.executions == 0:
            return 0.0

        return round(
            (self.successful_executions / self.executions) * 100,
            2,
        )

    def average_duration(
        self,
    ) -> float:
        """
        Calculate average execution duration.
        """

        if self.executions == 0:
            return 0.0

        return round(
            self.total_duration_ms / self.executions,
            2,
        )

    def health(
        self,
    ) -> AgentHealth:
        """
        Build current agent health snapshot.
        """

        return AgentHealth(
            healthy=(
                self.status
                in [
                    AgentStatus.READY,
                    AgentStatus.EXECUTING,
                ]
                and self.configuration.enabled
            ),
            status=self.status.value,
            executions=self.executions,
            successful_executions=(self.successful_executions),
            failed_executions=(self.failed_executions),
            average_duration_ms=(self.average_duration()),
            last_execution_at=(self.last_execution_at),
            last_error=self.last_error,
            metadata={
                "agent_id": str(self.id),
                "enabled": (self.configuration.enabled),
                "success_rate": (self.success_rate()),
            },
        )
