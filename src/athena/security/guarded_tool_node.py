from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from athena.permissions.engine import PermissionEngine
from athena.schemas import PermissionRequest

ToolCallable = Callable[..., Awaitable[Any]]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str = ''


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    content: Any
    permission_required: PermissionRequest | None = None


@dataclass
class GuardedToolExecutor:
    tools: dict[str, ToolCallable]
    permission_engine: PermissionEngine = field(default_factory=PermissionEngine)

    async def execute(self, task_id: str, call: ToolCall, session_id: str = 'default') -> ToolResult:
        request = PermissionRequest(task_id=task_id, tool_name=call.name, args=call.args)
        verdict = self.permission_engine.check(request, session_id=session_id)
        if verdict == 'deny':
            return ToolResult(call.name, False, f'tool denied: {request.reason}')
        if verdict == 'ask':
            return ToolResult(call.name, False, 'permission required', permission_required=request)
        tool = self.tools.get(call.name)
        if not tool:
            return ToolResult(call.name, False, f'unknown tool: {call.name}')
        try:
            content = await tool(**call.args)
            return ToolResult(call.name, True, content)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(call.name, False, str(exc))
