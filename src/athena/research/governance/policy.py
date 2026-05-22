"""Approval policy for Research OS tool calls."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.tools import PermissionLevel, ToolSpec


class ApprovalDecision(BaseModel):
    required: bool
    allowed: bool = True
    reason: str | None = None
    risk_level: str = "low"


class ApprovalPolicy:
    """Production-oriented default policy for tool execution."""

    def check_tool_call(self, tool: ToolSpec, _arguments: dict) -> ApprovalDecision:
        permission = tool.permission_level

        if permission is PermissionLevel.destructive:
            return ApprovalDecision(
                required=True,
                allowed=False,
                reason="destructive tools are denied by default",
                risk_level="critical",
            )
        if permission in {
            PermissionLevel.write_repo,
            PermissionLevel.run_local_command,
            PermissionLevel.run_expensive_job,
            PermissionLevel.external_side_effect,
        }:
            return ApprovalDecision(
                required=True,
                reason=f"{permission.value} requires human approval",
                risk_level="high" if permission is not PermissionLevel.write_repo else "medium",
            )
        if permission is PermissionLevel.write_artifact:
            return ApprovalDecision(
                required=False,
                reason="artifact writes are allowed but must be recorded",
                risk_level="medium",
            )
        if permission is PermissionLevel.network_read:
            return ApprovalDecision(
                required=False,
                reason="network reads are allowed with cost/rate limits",
                risk_level="low",
            )
        return ApprovalDecision(required=False, reason="read-only tool", risk_level="low")
