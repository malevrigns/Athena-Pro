"""Tests for the default Research OS tool registry."""

from __future__ import annotations

import pytest

from athena.research.tools.registry import build_research_tool_router

_EXPECTED_TOOLS = {
    "paper_search",
    "paper_reader",
    "citation_graph",
    "claim_extract",
    "taxonomy_build",
    "baseline_extract",
    "baseline_rank",
    "benchmark_extract",
    "idea_rank",
}


@pytest.mark.asyncio
async def test_registry_assembles_the_full_research_toolset(make_store):
    repo = await make_store().research_repository()
    router = build_research_tool_router(repo)
    assert set(router.names()) == _EXPECTED_TOOLS
    # every registered tool exposes an LLM-facing spec.
    assert len(router.specs_for_llm()) == len(_EXPECTED_TOOLS)
