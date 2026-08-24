from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    display_name: str
    description: str
    capability_type: str
    input_schema: dict
    output_schema: dict
    risk_level: str = "low"
    approval_required: bool = False
    version: str = "1.0.0"


class EnterpriseConnector(ABC):
    connector_type: str

    @abstractmethod
    def validate_configuration(self, connection, secret: dict) -> None: ...

    @abstractmethod
    async def test_connection(self, connection, secret: dict) -> dict: ...

    @abstractmethod
    async def discover_capabilities(
        self, connection, secret: dict
    ) -> tuple[list[CapabilityDefinition], dict]: ...

    async def health_check(self, connection, secret: dict) -> dict:
        return await self.test_connection(connection, secret)

    @abstractmethod
    async def execute_tool(
        self, connection, capability: str, arguments: dict, secret: dict
    ) -> Any: ...

    @abstractmethod
    async def execute_action(
        self, connection, capability: str, arguments: dict, secret: dict
    ) -> Any: ...
