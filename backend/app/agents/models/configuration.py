from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfiguration:
    """
    Runtime configuration for an enterprise agent.

    Controls:
    - Availability
    - Execution limits
    - Runtime behavior
    - Custom configuration
    """

    # --------------------------------------------------
    # Agent Availability
    # --------------------------------------------------

    enabled: bool = True

    # --------------------------------------------------
    # Execution Management
    # --------------------------------------------------

    timeout_seconds: int = 60

    max_concurrent_tasks: int = 5

    retry_count: int = 0

    # --------------------------------------------------
    # Runtime Metadata
    # --------------------------------------------------

    metadata: dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------
    # Backward Compatibility Alias
    # --------------------------------------------------

    @property
    def max_concurrency(
        self,
    ) -> int:
        """
        Alias for max_concurrent_tasks.

        Kept for API compatibility.
        """

        return self.max_concurrent_tasks

    @max_concurrency.setter
    def max_concurrency(
        self,
        value: int,
    ) -> None:
        """
        Update max concurrency.
        """

        self.max_concurrent_tasks = value
