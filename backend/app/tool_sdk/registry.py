from __future__ import annotations

import asyncio
from collections import OrderedDict

from app.contracts.tool import Tool
from app.tool_sdk.errors import ToolNotFoundError, ToolVersionNotFoundError


def _version_key(v: str):
    return tuple(int(x) for x in v.split("-")[0].split("+")[0].split("."))


class ToolRegistry:
    def __init__(self):
        self._tools: OrderedDict[tuple[str, str], Tool] = OrderedDict()
        self._active: dict[str, str] = {}
        self._disabled: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()

    def register(self, tool: Tool, *, active=True):
        key = (tool.metadata.name, tool.metadata.version)
        if key in self._tools:
            raise ValueError(
                f"Tool '{key[0]}' version '{key[1]}' is already registered"
            )
        self._tools[key] = tool
        if active or key[0] not in self._active:
            self._active[key[0]] = key[1]

    def register_many(self, tools):
        for tool in sorted(
            tools, key=lambda x: (x.metadata.name, _version_key(x.metadata.version))
        ):
            self.register(tool)

    def unregister(self, name, version):
        self._tools.pop((name, version), None)
        if self._active.get(name) == version:
            versions = self.versions(name)
            self._active[name] = versions[-1] if versions else None

    def get(self, name, version=None):
        if not any(n == name for n, _ in self._tools):
            raise ToolNotFoundError(f"Tool '{name}' was not found")
        version = version or self._active.get(name)
        try:
            return self._tools[(name, version)]
        except KeyError:
            raise ToolVersionNotFoundError(
                f"Tool '{name}' version '{version}' was not found"
            ) from None

    def versions(self, name):
        return sorted([v for n, v in self._tools if n == name], key=_version_key)

    def set_active(self, name, version):
        self.get(name, version)
        self._active[name] = version

    def set_enabled(self, name, version, enabled):
        key = (name, version)
        self.get(*key)
        self._disabled.discard(key) if enabled else self._disabled.add(key)

    def is_enabled(self, tool):
        return (
            tool.metadata.enabled
            and (tool.metadata.name, tool.metadata.version) not in self._disabled
        )

    def list(self, **filters):
        result = []
        for tool in self._tools.values():
            m = tool.metadata
            if filters.get("category") and m.category != filters["category"]:
                continue
            if filters.get("provider") and m.provider != filters["provider"]:
                continue
            if filters.get("risk_level") and m.risk_level != filters["risk_level"]:
                continue
            if filters.get("tag") and filters["tag"] not in m.tags:
                continue
            if filters.get("permission") and filters["permission"] not in m.permissions:
                continue
            if (
                filters.get("enabled") is not None
                and self.is_enabled(tool) != filters["enabled"]
            ):
                continue
            result.append(tool)
        return result
