"""Default Research OS tool registry.

`build_research_tool_router` assembles every research tool into one
`ToolRouter` — the tool surface an agent loop is given when it runs a project.
Keeping the assembly here means the API run endpoint and any future runtime
entry share exactly one definition of "the research toolset".
"""

from __future__ import annotations

from athena.research.persistence import ResearchRepository
from athena.tools.search import SearchClient

from .baseline_tools import build_baseline_extract_tool, build_baseline_rank_tool
from .citation_graph import build_citation_graph_tool
from .evidence_tools import build_claim_extract_tool
from .idea_tools import build_idea_rank_tool
from .paper_reader import build_paper_reader_tool
from .paper_search import build_paper_search_tool
from .router import ToolRouter
from .taxonomy_tools import build_taxonomy_tool

# Tool builders that take only the repository. paper_search is handled
# separately because it also accepts a search client.
_REPO_ONLY_BUILDERS = (
    build_paper_reader_tool,
    build_citation_graph_tool,
    build_claim_extract_tool,
    build_taxonomy_tool,
    build_baseline_extract_tool,
    build_baseline_rank_tool,
    build_idea_rank_tool,
)


def build_research_tool_router(
    repository: ResearchRepository,
    *,
    search_client: SearchClient | None = None,
) -> ToolRouter:
    """Build a ToolRouter holding the full Research OS toolset."""
    router = ToolRouter([build_paper_search_tool(repository, search_client)])
    for build in _REPO_ONLY_BUILDERS:
        router.register(build(repository))
    return router
