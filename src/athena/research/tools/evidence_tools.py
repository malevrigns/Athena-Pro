"""Evidence tools for Research OS: claim extraction backed by the claims service."""

from __future__ import annotations

from pydantic import BaseModel

from athena.research.persistence import ResearchRepository
from athena.research.services.claims import extract_claims

from .base import PermissionLevel, ToolResult, ToolSpec


class ClaimExtractArguments(BaseModel):
    project_id: str
    paper_id: str


def build_claim_extract_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = ClaimExtractArguments.model_validate(arguments)
        try:
            result = await extract_claims(
                repository,
                project_id=args.project_id,
                paper_id=args.paper_id,
            )
        except LookupError as exc:
            return ToolResult(ok=False, summary=str(exc), error="not_found")

        return ToolResult(
            ok=True,
            summary=(
                f"extracted {len(result.claims)} claims and {len(result.evidence)} "
                f"evidence records from {result.extraction_source}"
            ),
            structured_output=result.to_payload(),
        )

    return ToolSpec(
        name="claim_extract",
        description=(
            "Extract grounded method/dataset/result/limitation/implementation claims "
            "for one project paper, persisting a linked Evidence record for each claim."
        ),
        parameters_schema=ClaimExtractArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.write_artifact,
        timeout_seconds=30,
        cost_level="low",
    )
