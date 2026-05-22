"""Tests for ResearchRuntimeState and ResearchSession (roadmap section 7)."""

from __future__ import annotations

import asyncio

import pytest

from athena.research.domain import Claim, ClaimType, Evidence, Paper, PaperNote, ResearchProject
from athena.research.runtime import (
    AgentStep,
    LoopOutcome,
    ResearchSession,
    ScriptedBrain,
    load_runtime_state,
)
from athena.research.tools import PermissionLevel, ToolResult, ToolRouter, ToolSpec


def _search_tool() -> ToolSpec:
    async def handler(arguments: dict) -> ToolResult:
        return ToolResult(ok=True, summary="found papers", structured_output={"args": arguments})

    return ToolSpec(
        name="paper_search",
        description="search papers",
        parameters_schema={"type": "object"},
        handler=handler,
        permission_level=PermissionLevel.network_read,
    )


async def _seed_project(repo) -> ResearchProject:
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    paper = Paper(project_id=project.id, title="RAG paper")
    await repo.create_paper(paper)
    await repo.create_paper_note(PaperNote(paper_id=paper.id, problem="QA"))
    claim = Claim(project_id=project.id, text="claim", claim_type=ClaimType.method)
    await repo.create_claim(claim)
    await repo.create_evidence(Evidence(claim_id=claim.id, source_type="paper_note"))
    return project


# --- ResearchRuntimeState -----------------------------------------------


@pytest.mark.asyncio
async def test_load_runtime_state_hydrates_persisted_assets(make_store):
    repo = await make_store().research_repository()
    project = await _seed_project(repo)

    state = await load_runtime_state(repo, project.id)

    assert state.project is not None and state.project.id == project.id
    counts = state.asset_counts()
    assert counts["papers"] == 1
    assert counts["paper_notes"] == 1
    assert counts["claims"] == 1
    assert counts["evidence"] == 1
    assert "project=RAG" in state.summary()


@pytest.mark.asyncio
async def test_load_runtime_state_rejects_unknown_project(make_store):
    repo = await make_store().research_repository()
    with pytest.raises(LookupError):
        await load_runtime_state(repo, "proj_missing")


# --- ResearchSession -----------------------------------------------------


@pytest.mark.asyncio
async def test_session_runs_the_agent_loop_without_review(make_store):
    repo = await make_store().research_repository()
    project = await _seed_project(repo)
    session = ResearchSession(repository=repo, router=ToolRouter([_search_tool()]), project=project)
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="paper_search", arguments={"q": "rag"}),
            AgentStep(kind="final", final_answer="done"),
        ]
    )

    result = await session.run(brain=brain, goal="survey RAG")

    assert result.started is True
    assert result.plan_review is None
    assert result.loop_result.outcome is LoopOutcome.completed
    assert result.state.tool_trace  # loop trace folded into runtime state
    # the loop's tool call was persisted to the trace tables.
    assert [c.tool_name for c in await repo.list_tool_calls(project.id)] == ["paper_search"]


@pytest.mark.asyncio
async def test_session_blocks_on_plan_review_and_runs_when_approved(make_store):
    from athena.research.domain import ReviewDecision

    repo = await make_store().research_repository()
    project = await _seed_project(repo)
    session = ResearchSession(repository=repo, router=ToolRouter([_search_tool()]), project=project)
    brain = ScriptedBrain(steps=[AgentStep(kind="final", final_answer="done")])

    run_task = asyncio.create_task(
        session.run(brain=brain, goal="survey RAG", plan={"steps": ["a"]}, require_plan_review=True)
    )
    pending = await _await_pending(session, project.id)
    await session.checkpoints.resolve(pending.id, ReviewDecision.approved)

    result = await asyncio.wait_for(run_task, timeout=2)
    assert result.started is True
    assert result.plan_review.decision is ReviewDecision.approved
    assert result.loop_result is not None


@pytest.mark.asyncio
async def test_session_does_not_run_when_plan_review_is_rejected(make_store):
    from athena.research.domain import ReviewDecision

    repo = await make_store().research_repository()
    project = await _seed_project(repo)
    session = ResearchSession(repository=repo, router=ToolRouter([_search_tool()]), project=project)
    brain = ScriptedBrain(steps=[AgentStep(kind="final", final_answer="unreachable")])

    run_task = asyncio.create_task(
        session.run(brain=brain, goal="survey RAG", require_plan_review=True)
    )
    pending = await _await_pending(session, project.id)
    await session.checkpoints.resolve(pending.id, ReviewDecision.rejected, comment="scope too broad")

    result = await asyncio.wait_for(run_task, timeout=2)
    assert result.started is False
    assert result.plan_review.decision is ReviewDecision.rejected
    assert result.loop_result is None  # the agent loop never started


async def _await_pending(session: ResearchSession, project_id: str):
    """Poll until the session has opened its (single) pending checkpoint."""
    for _ in range(100):
        pending = await session.checkpoints.list_pending(project_id)
        if pending:
            return pending[0]
        await asyncio.sleep(0.01)
    raise AssertionError("no pending checkpoint appeared")
