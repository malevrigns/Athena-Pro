"""Benchmark tool for Research OS, backed by the benchmark extraction service."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.persistence import ResearchRepository
from athena.research.services.benchmarks import extract_benchmark_candidates

from .base import PermissionLevel, ToolResult, ToolSpec


class BenchmarkExtractArguments(BaseModel):
    project_id: str


def build_benchmark_extract_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = BenchmarkExtractArguments.model_validate(arguments)
        try:
            created = await extract_benchmark_candidates(repository, args.project_id)
        except LookupError as exc:
            return ToolResult(ok=False, summary=str(exc), error="not_found")
        return ToolResult(
            ok=True,
            summary=f"extracted {len(created)} benchmark candidates",
            structured_output={
                "project_id": args.project_id,
                "created_count": len(created),
                "benchmarks": [b.model_dump(mode="json") for b in created],
            },
        )

    return ToolSpec(
        name="benchmark_extract",
        description="Derive evaluation benchmark candidates from the datasets a project's "
        "papers are evaluated on, ranked by adoption.",
        parameters_schema=BenchmarkExtractArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )
