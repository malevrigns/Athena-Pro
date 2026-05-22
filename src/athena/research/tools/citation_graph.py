"""Citation-graph tool for Research OS (roadmap section 6.1).

This tool does not call an external citation API. It derives a *relatedness*
graph over the papers already collected in a project: two papers are linked
when they share datasets, authors, or title vocabulary. Given a focus paper it
splits its neighbours into `references` (same year or older) and `citations`
(newer), which is the structural shape callers expect from a citation graph.

Keeping it offline makes the tool deterministic and testable; a real Semantic
Scholar / OpenAlex provider can later replace `_relatedness` without changing
the output contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.research.domain import Paper
from athena.research.persistence import ResearchRepository

from .base import PermissionLevel, ToolResult, ToolSpec

# Common words that carry no topical signal when comparing paper titles.
_TITLE_STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "with",
        "via", "using", "from", "by", "as", "at", "is", "are", "be", "we",
        "our", "this", "that", "towards", "toward", "into", "over", "based",
    }
)


class CitationGraphArguments(BaseModel):
    project_id: str
    paper_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class CitationGraphNode(BaseModel):
    paper_id: str
    title: str
    year: int | None = None
    citation_count: int | None = None
    screening_status: str


class CitationGraphEdge(BaseModel):
    source: str
    target: str
    score: float
    shared_datasets: int
    shared_authors: int
    title_overlap: float


class CitationNeighbor(BaseModel):
    paper_id: str
    title: str
    year: int | None = None
    citation_count: int | None = None
    score: float


class CitationGraphPayload(BaseModel):
    project_id: str
    paper_id: str | None
    node_count: int
    edge_count: int
    nodes: list[CitationGraphNode]
    edges: list[CitationGraphEdge]
    references: list[CitationNeighbor]
    citations: list[CitationNeighbor]
    influential_citations: list[CitationNeighbor]


def build_citation_graph_tool(repository: ResearchRepository) -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        args = CitationGraphArguments.model_validate(arguments)
        project = await repository.get_project(args.project_id)
        if project is None:
            return ToolResult(ok=False, summary="project not found", error="project_not_found")

        papers = await repository.list_project_papers(args.project_id, limit=500)
        by_id = {paper.id: paper for paper in papers}
        if args.paper_id is not None and args.paper_id not in by_id:
            return ToolResult(ok=False, summary="paper not found", error="paper_not_found")

        edges = _build_edges(papers)
        nodes = [
            CitationGraphNode(
                paper_id=paper.id,
                title=paper.title,
                year=paper.year,
                citation_count=paper.citation_count,
                screening_status=paper.screening_status.value,
            )
            for paper in papers
        ]

        references: list[CitationNeighbor] = []
        citations: list[CitationNeighbor] = []
        influential: list[CitationNeighbor] = []
        if args.paper_id is not None:
            references, citations, influential = _split_neighbors(
                by_id[args.paper_id], by_id, edges, limit=args.limit
            )

        payload = CitationGraphPayload(
            project_id=args.project_id,
            paper_id=args.paper_id,
            node_count=len(nodes),
            edge_count=len(edges),
            nodes=nodes,
            edges=edges,
            references=references,
            citations=citations,
            influential_citations=influential,
        )
        if args.paper_id is None:
            summary = f"built relatedness graph: {len(nodes)} papers, {len(edges)} edges"
        else:
            summary = (
                f"{len(references)} references, {len(citations)} citations "
                f"for paper {args.paper_id}"
            )
        return ToolResult(ok=True, summary=summary, structured_output=payload.model_dump(mode="json"))

    return ToolSpec(
        name="citation_graph",
        description=(
            "Build a relatedness graph over a project's papers (shared datasets, "
            "authors, title terms); optionally split one paper's neighbours into "
            "references and citations by publication year."
        ),
        parameters_schema=CitationGraphArguments.model_json_schema(),
        handler=handler,
        permission_level=PermissionLevel.read_only,
        timeout_seconds=15,
        cost_level="low",
    )


def _build_edges(papers: list[Paper]) -> list[CitationGraphEdge]:
    edges: list[CitationGraphEdge] = []
    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            score, datasets, authors, overlap = _relatedness(papers[i], papers[j])
            if datasets == 0 and authors == 0 and overlap < 0.2:
                continue
            edges.append(
                CitationGraphEdge(
                    source=papers[i].id,
                    target=papers[j].id,
                    score=round(score, 3),
                    shared_datasets=datasets,
                    shared_authors=authors,
                    title_overlap=overlap,
                )
            )
    edges.sort(key=lambda edge: edge.score, reverse=True)
    return edges


def _split_neighbors(
    focus: Paper,
    by_id: dict[str, Paper],
    edges: list[CitationGraphEdge],
    *,
    limit: int,
) -> tuple[list[CitationNeighbor], list[CitationNeighbor], list[CitationNeighbor]]:
    """Split a focus paper's graph neighbours into references / citations.

    A neighbour newer than the focus paper is treated as a `citation` (it could
    cite the focus); a same-year, older, or undated neighbour is a `reference`.
    `influential_citations` are the highest-cited citations, falling back to all
    neighbours when no year information is available to split on.
    """
    neighbors: list[tuple[Paper, float]] = []
    for edge in edges:
        if edge.source == focus.id:
            neighbors.append((by_id[edge.target], edge.score))
        elif edge.target == focus.id:
            neighbors.append((by_id[edge.source], edge.score))

    references: list[CitationNeighbor] = []
    citations: list[CitationNeighbor] = []
    for paper, score in neighbors:
        neighbor = CitationNeighbor(
            paper_id=paper.id,
            title=paper.title,
            year=paper.year,
            citation_count=paper.citation_count,
            score=score,
        )
        if focus.year is not None and paper.year is not None and paper.year > focus.year:
            citations.append(neighbor)
        else:
            references.append(neighbor)

    pool = citations or [*references, *citations]
    influential = sorted(
        pool,
        key=lambda n: (n.citation_count or 0, n.score),
        reverse=True,
    )[:limit]
    return references, citations, influential


def _relatedness(a: Paper, b: Paper) -> tuple[float, int, int, float]:
    datasets = len(_norm_set(a.dataset_mentions) & _norm_set(b.dataset_mentions))
    authors = len(_norm_set(a.authors) & _norm_set(b.authors))
    overlap = _jaccard(_title_tokens(a.title), _title_tokens(b.title))
    score = 2.0 * datasets + 2.0 * authors + overlap
    return score, datasets, authors, round(overlap, 3)


def _norm_set(values: list[str]) -> set[str]:
    return {" ".join(value.strip().lower().split()) for value in values if value.strip()}


def _title_tokens(title: str) -> set[str]:
    tokens: set[str] = set()
    word = []
    for char in title.lower():
        if char.isalnum():
            word.append(char)
        elif word:
            tokens.add("".join(word))
            word = []
    if word:
        tokens.add("".join(word))
    return {token for token in tokens if len(token) >= 3 and token not in _TITLE_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
