"""Paper Reader tool backed by the Research OS PaperNote extraction service."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.persistence import ResearchRepository
from athena.research.services.paper_reader import extract_paper_note

from .base import PermissionLevel, ToolResult, ToolSpec


class PaperReaderArguments(BaseModel):
    project_id: str
    paper_id: str


def build_paper_reader_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = PaperReaderArguments.model_validate(arguments)
        try:
            extraction = await extract_paper_note(
                repository,
                project_id=args.project_id,
                paper_id=args.paper_id,
            )
        except LookupError as exc:
            return ToolResult(ok=False, summary=str(exc), error="not_found")

        return ToolResult(
            ok=True,
            summary=f"extracted PaperNote {extraction.note.id}",
            structured_output=extraction.to_tool_payload(
                project_id=args.project_id,
                paper_id=args.paper_id,
            ),
        )

    return ToolSpec(
        name="paper_reader",
        description="Extract a structured PaperNote for one project paper using the long Paper Reader node prompt.",
        parameters_schema=PaperReaderArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=90,
        cost_level="medium",
    )
