"""Tool registry and execution router for Research OS."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from .base import ToolResult, ToolSpec


class ToolRouter:
    """Registry and execution boundary for Research OS tools."""

    def __init__(self, tools: list[ToolSpec] | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs_for_llm(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        try:
            value = tool.handler(arguments)
            if inspect.isawaitable(value):
                value = await asyncio.wait_for(value, timeout=tool.timeout_seconds)
            result = ToolResult.model_validate(value)
            return result
        except TimeoutError:
            return ToolResult(
                ok=False,
                summary=f"tool timed out after {tool.timeout_seconds:g}s",
                error="timeout",
            )
        except Exception as exc:
            return ToolResult(ok=False, summary=str(exc), error=exc.__class__.__name__)

