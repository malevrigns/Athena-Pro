"""Taxonomy tool for Research OS, backed by the taxonomy build service."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.persistence import ResearchRepository
from athena.research.services.taxonomy import build_taxonomy

from .base import PermissionLevel, ToolResult, ToolSpec


class TaxonomyBuildArguments(BaseModel):
    project_id: str


def build_taxonomy_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = TaxonomyBuildArguments.model_validate(arguments)
        try:
            taxonomy = await build_taxonomy(repository, args.project_id)
        except LookupError as exc:
            return ToolResult(ok=False, summary=str(exc), error="not_found")
        return ToolResult(
            ok=True,
            summary=taxonomy.summary or f"built taxonomy {taxonomy.id}",
            structured_output=taxonomy.model_dump(mode="json"),
        )

    return ToolSpec(
        name="taxonomy_build",
        description="Build a method taxonomy (method families, datasets, evaluation protocols) "
        "from a project's papers and reading notes.",
        parameters_schema=TaxonomyBuildArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )
