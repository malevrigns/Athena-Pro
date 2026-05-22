"""Idea tool for Research OS, backed by the idea ranking service."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.persistence import ResearchRepository
from athena.research.services.ideas import rank_ideas

from .base import PermissionLevel, ToolResult, ToolSpec


class IdeaRankArguments(BaseModel):
    project_id: str


def build_idea_rank_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = IdeaRankArguments.model_validate(arguments)
        scores = await rank_ideas(repository, args.project_id)
        return ToolResult(
            ok=True,
            summary=f"ranked {len(scores)} ideas",
            structured_output={
                "project_id": args.project_id,
                "ranking": [s.model_dump(mode="json") for s in scores],
            },
        )

    return ToolSpec(
        name="idea_rank",
        description="Score and rank a project's research ideas on seven weighted axes.",
        parameters_schema=IdeaRankArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )
