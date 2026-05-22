from __future__ import annotations

import pytest

from athena.research.governance import ApprovalPolicy
from athena.research.tools import PermissionLevel, ToolResult, ToolSpec


async def _handler(_arguments: dict) -> ToolResult:
    return ToolResult(ok=True, summary="ok")


def _tool(permission: PermissionLevel) -> ToolSpec:
    return ToolSpec(
        name=f"tool_{permission.value}",
        description="test tool",
        parameters_schema={"type": "object"},
        handler=_handler,
        permission_level=permission,
    )


@pytest.mark.parametrize("permission", [PermissionLevel.read_only, PermissionLevel.network_read])
def test_low_risk_tools_do_not_require_approval(permission):
    decision = ApprovalPolicy().check_tool_call(_tool(permission), {})

    assert decision.allowed is True
    assert decision.required is False
    assert decision.risk_level == "low"


def test_write_artifact_is_allowed_but_marked_medium_risk():
    decision = ApprovalPolicy().check_tool_call(_tool(PermissionLevel.write_artifact), {})

    assert decision.allowed is True
    assert decision.required is False
    assert decision.risk_level == "medium"


@pytest.mark.parametrize(
    "permission",
    [
        PermissionLevel.write_repo,
        PermissionLevel.run_local_command,
        PermissionLevel.run_expensive_job,
        PermissionLevel.external_side_effect,
    ],
)
def test_high_impact_tools_require_human_approval(permission):
    decision = ApprovalPolicy().check_tool_call(_tool(permission), {})

    assert decision.allowed is True
    assert decision.required is True
    assert permission.value in (decision.reason or "")


def test_destructive_tools_are_denied_by_default():
    decision = ApprovalPolicy().check_tool_call(_tool(PermissionLevel.destructive), {})

    assert decision.allowed is False
    assert decision.required is True
    assert decision.risk_level == "critical"

