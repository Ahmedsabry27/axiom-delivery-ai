from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class RuntimeStep:
    name: str

    description: str

    status: str = "pending"

    started_at: datetime | None = None

    completed_at: datetime | None = None


@dataclass
class RuntimeExecution:
    execution_id: str = field(default_factory=lambda: str(uuid4()))

    workflow_id: str | None = None

    status: str = "RUNNING"

    agent: str | None = None

    duration_ms: int = 0

    steps: list[RuntimeStep] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_step(self, name: str, description: str, status: str = "pending"):

        self.steps.append(
            RuntimeStep(name=name, description=description, status=status)
        )
