"""Shared execution path for Research OS tools with durable trace records."""

from __future__ import annotations

from athena.research.persistence import ResearchRepository
from athena.research.tools import (
    ToolCallRecord,
    ToolCallStatus,
    ToolObservationRecord,
    ToolObservationStatus,
    ToolResult,
    ToolRouter,
    utcnow,
)


async def execute_tool_with_trace(
    repository: ResearchRepository,
    router: ToolRouter,
    *,
    task_id: str,
    project_id: str | None,
    tool_name: str,
    arguments: dict,
) -> ToolResult:
    spec = router.get(tool_name)
    started_at = utcnow()
    result = await router.execute(tool_name, arguments)
    finished_at = utcnow()
    call = ToolCallRecord(
        task_id=task_id,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
        permission_level=spec.permission_level,
        approval_status="not_required",
        status=ToolCallStatus.completed if result.ok else ToolCallStatus.failed,
        started_at=started_at,
        finished_at=finished_at,
    )
    await repository.record_tool_call(call)
    await repository.record_tool_observation(
        ToolObservationRecord(
            tool_call_id=call.id,
            status=ToolObservationStatus.ok if result.ok else ToolObservationStatus.error,
            summary=result.summary,
            structured_output=result.structured_output,
            raw_output_ref=result.raw_output_ref,
            error=result.error,
        )
    )
    return result
