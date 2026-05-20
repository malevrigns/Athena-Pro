from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class MCPTool:
    name: str
    description: str
    schema: dict[str, Any]
    call: Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class MCPToolAdapter:
    tool: MCPTool

    async def ainvoke(self, args: dict[str, Any]) -> Any:
        return await self.tool.call(args)

    def as_schema(self) -> dict[str, Any]:
        return {"name": self.tool.name, "description": self.tool.description, "parameters": self.tool.schema}
