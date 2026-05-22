"""Baseline tools for Research OS: candidate extraction and multi-axis ranking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.research.persistence import ResearchRepository
from athena.research.services.baselines import extract_baseline_candidates, rank_baselines

from .base import PermissionLevel, ToolResult, ToolSpec


class BaselineExtractArguments(BaseModel):
    project_id: str


class BaselineRankArguments(BaseModel):
    project_id: str
    goal: str = Field(default="", max_length=2000)


def build_baseline_extract_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = BaselineExtractArguments.model_validate(arguments)
        try:
            created = await extract_baseline_candidates(repository, args.project_id)
        except LookupError as exc:
            return ToolResult(ok=False, summary=str(exc), error="not_found")
        return ToolResult(
            ok=True,
            summary=f"extracted {len(created)} baseline candidates",
            structured_output={
                "project_id": args.project_id,
                "created_count": len(created),
                "baselines": [b.model_dump(mode="json") for b in created],
            },
        )

    return ToolSpec(
        name="baseline_extract",
        description="Derive baseline candidates from papers that have a method reading note.",
        parameters_schema=BaselineExtractArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )


def build_baseline_rank_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = BaselineRankArguments.model_validate(arguments)
        scores = await rank_baselines(repository, args.project_id, goal=args.goal)
        return ToolResult(
            ok=True,
            summary=f"ranked {len(scores)} baselines",
            structured_output={
                "project_id": args.project_id,
                "ranking": [s.model_dump(mode="json") for s in scores],
            },
        )

    return ToolSpec(
        name="baseline_rank",
        description="Score and rank a project's baseline candidates on seven weighted axes.",
        parameters_schema=BaselineRankArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )
