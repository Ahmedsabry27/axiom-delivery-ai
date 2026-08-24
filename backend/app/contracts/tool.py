from abc import ABC, abstractmethod

from app.contracts.tool_models import ExecutionContext, ToolMetadata, ToolResult


class Tool(ABC):
    """
    Base contract for enterprise tools.
    """

    metadata: ToolMetadata

    @property
    def name(self) -> str:
        return self.metadata.name

    @abstractmethod
    async def execute(
        self,
        input_data: dict,
        context: ExecutionContext,
    ) -> ToolResult: ...

    async def health(self) -> dict:
        return {"ready": True, "message": "Ready"}
