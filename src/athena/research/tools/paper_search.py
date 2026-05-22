"""Paper search tool backed by Athena's existing search providers."""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.research.domain import Paper
from athena.research.persistence import ResearchRepository
from athena.tools.search import SearchClient

from .base import PermissionLevel, ToolResult, ToolSpec


class PaperSearchArguments(BaseModel):
    project_id: str
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class PaperSearchPayload(BaseModel):
    project_id: str
    query: str
    result_count: int
    created_count: int
    skipped_duplicates: int
    papers: list[Paper]


def build_paper_search_tool(
    repository: ResearchRepository,
    search_client: SearchClient | None = None,
) -> ToolSpec:
    client = search_client or SearchClient()

    async def handler(arguments: dict) -> ToolResult:
        args = PaperSearchArguments.model_validate(arguments)
        project = await repository.get_project(args.project_id)
        if project is None:
            return ToolResult(ok=False, summary="project not found", error="project_not_found")

        existing = await repository.list_project_papers(args.project_id, limit=500)
        existing_keys = {_paper_key(paper) for paper in existing}
        results = await client.web_search(args.query, max_results=args.limit)
        created: list[Paper] = []
        skipped = 0

        for result in results:
            paper = Paper(
                project_id=args.project_id,
                title=result.title,
                abstract=result.snippet or None,
                url=result.url,
                relevance_score=result.score,
            )
            key = _paper_key(paper)
            if key in existing_keys:
                skipped += 1
                continue
            await repository.create_paper(paper)
            existing_keys.add(key)
            created.append(paper)

        return ToolResult(
            ok=True,
            summary=f"found {len(results)} results, added {len(created)} papers",
            structured_output=PaperSearchPayload(
                project_id=args.project_id,
                query=args.query,
                result_count=len(results),
                created_count=len(created),
                skipped_duplicates=skipped,
                papers=created,
            ).model_dump(mode="json"),
        )

    return ToolSpec(
        name="paper_search",
        description="Search the web for papers and persist new results as project Paper assets.",
        parameters_schema=PaperSearchArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.network_read,
        timeout_seconds=30,
        cost_level="low",
    )


def _paper_key(paper: Paper) -> tuple[str, str]:
    url = (paper.url or "").strip().lower()
    title = " ".join(paper.title.strip().lower().split())
    return url, title
