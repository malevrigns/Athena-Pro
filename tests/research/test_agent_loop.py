"""Tests for the Research OS agent loop (roadmap section 7.1)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from athena.research.runtime import (
    AgentLoop,
    AgentStep,
    LLMAgentBrain,
    LoopContext,
    LoopLimits,
    LoopOutcome,
    ScriptedBrain,
    StepUsage,
    auto_approve,
)
from athena.research.runtime.loop import _compact
from athena.research.tools import PermissionLevel, ToolResult, ToolRouter, ToolSpec


# --- tool / brain fixtures ----------------------------------------------


def _tool(name: str, *, permission=PermissionLevel.read_only, handler=None) -> ToolSpec:
    async def default_handler(arguments: dict) -> ToolResult:
        return ToolResult(ok=True, summary=f"{name} ran", structured_output={"args": arguments})

    return ToolSpec(
        name=name,
        description=f"{name} tool",
        parameters_schema={"type": "object"},
        handler=handler or default_handler,
        permission_level=permission,
    )


@dataclass
class CountingToolBrain:
    """Always calls one tool; arguments vary each turn so signatures differ."""

    tool_name: str

    async def decide(self, context: LoopContext) -> AgentStep:
        return AgentStep(
            kind="tool_call",
            tool_name=self.tool_name,
            arguments={"iteration": context.iteration},
        )


@dataclass
class RepeatBrain:
    """Always issues the identical tool call — a doom loop."""

    tool_name: str

    async def decide(self, _context: LoopContext) -> AgentStep:
        return AgentStep(kind="tool_call", tool_name=self.tool_name, arguments={"q": "same"})


class BoomBrain:
    async def decide(self, _context: LoopContext) -> AgentStep:
        raise RuntimeError("brain exploded")


# --- happy path ----------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_calls_tool_then_finishes():
    router = ToolRouter([_tool("paper_search", permission=PermissionLevel.network_read)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="paper_search", arguments={"q": "rag"}),
            AgentStep(kind="final", final_answer="surveyed RAG"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router).run("survey RAG")

    assert result.outcome is LoopOutcome.completed
    assert result.final_answer == "surveyed RAG"
    assert result.usage.tool_calls == 1
    assert [s.kind for s in result.steps] == ["tool_call", "final"]
    assert result.steps[0].ok is True


# --- budgets -------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_stops_at_max_iterations():
    router = ToolRouter([_tool("search")])
    result = await AgentLoop(
        brain=CountingToolBrain("search"),
        router=router,
        limits=LoopLimits(max_iterations=3, max_tool_calls=99),
    ).run("never ends")

    assert result.outcome is LoopOutcome.max_iterations
    assert result.usage.iterations == 3


@pytest.mark.asyncio
async def test_loop_stops_at_max_tool_calls():
    router = ToolRouter([_tool("search")])
    result = await AgentLoop(
        brain=CountingToolBrain("search"),
        router=router,
        limits=LoopLimits(max_iterations=99, max_tool_calls=2),
    ).run("never ends")

    assert result.outcome is LoopOutcome.max_tool_calls
    assert result.usage.tool_calls == 2


@pytest.mark.asyncio
async def test_loop_stops_when_token_budget_exceeded():
    router = ToolRouter([_tool("search")])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="search", arguments={"n": 1},
                      usage=StepUsage(input_tokens=60, output_tokens=0)),
            AgentStep(kind="tool_call", tool_name="search", arguments={"n": 2},
                      usage=StepUsage(input_tokens=60, output_tokens=0)),
            AgentStep(kind="final", final_answer="unreachable"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router, limits=LoopLimits(token_budget=100)).run("g")

    assert result.outcome is LoopOutcome.token_budget_exceeded
    assert result.usage.input_tokens == 120


@pytest.mark.asyncio
async def test_loop_stops_when_cost_budget_exceeded():
    router = ToolRouter([_tool("search")])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="search", arguments={"n": 1},
                      usage=StepUsage(input_tokens=600, output_tokens=0)),
            AgentStep(kind="tool_call", tool_name="search", arguments={"n": 2},
                      usage=StepUsage(input_tokens=600, output_tokens=0)),
            AgentStep(kind="final", final_answer="unreachable"),
        ]
    )
    result = await AgentLoop(
        brain=brain,
        router=router,
        limits=LoopLimits(usd_per_1k_tokens=10.0, cost_budget_usd=1.0),
    ).run("g")

    assert result.outcome is LoopOutcome.cost_budget_exceeded
    assert result.usage.cost_usd >= 1.0


# --- cancellation & repetition ------------------------------------------


@pytest.mark.asyncio
async def test_loop_honors_cancellation():
    router = ToolRouter([_tool("search")])
    cancel = asyncio.Event()
    cancel.set()
    result = await AgentLoop(brain=CountingToolBrain("search"), router=router, cancel=cancel).run("g")

    assert result.outcome is LoopOutcome.cancelled
    assert result.usage.iterations == 0


@pytest.mark.asyncio
async def test_loop_aborts_on_repeated_tool_call():
    router = ToolRouter([_tool("search")])
    result = await AgentLoop(
        brain=RepeatBrain("search"),
        router=router,
        limits=LoopLimits(repetition_threshold=3),
    ).run("g")

    assert result.outcome is LoopOutcome.repetition_aborted
    # the call ran twice before the third identical attempt was blocked.
    assert result.usage.tool_calls == 2
    assert result.steps[-1].error == "loop_repetition"


# --- approval ------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_required_tool_is_denied_by_default():
    router = ToolRouter([_tool("write_repo_tool", permission=PermissionLevel.write_repo)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="write_repo_tool", arguments={}),
            AgentStep(kind="final", final_answer="done without writing"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router).run("g")

    assert result.outcome is LoopOutcome.completed
    assert result.usage.tool_calls == 0  # never executed
    assert result.steps[0].approval_required is True
    assert result.steps[0].approval_granted is False
    assert result.steps[0].error == "approval_denied"


@pytest.mark.asyncio
async def test_approval_handler_can_grant_a_tool():
    router = ToolRouter([_tool("write_repo_tool", permission=PermissionLevel.write_repo)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="write_repo_tool", arguments={}),
            AgentStep(kind="final", final_answer="written"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router, approval_handler=auto_approve).run("g")

    assert result.usage.tool_calls == 1
    assert result.steps[0].approval_granted is True
    assert result.steps[0].ok is True


@pytest.mark.asyncio
async def test_destructive_tool_is_denied_even_with_auto_approve():
    router = ToolRouter([_tool("rm", permission=PermissionLevel.destructive)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="rm", arguments={}),
            AgentStep(kind="final", final_answer="safe"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router, approval_handler=auto_approve).run("g")

    assert result.usage.tool_calls == 0
    assert result.steps[0].approval_granted is False


# --- validation & error recovery ----------------------------------------


@pytest.mark.asyncio
async def test_unknown_tool_and_missing_name_are_rejected():
    router = ToolRouter([_tool("search")])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="ghost", arguments={}),
            AgentStep(kind="tool_call", tool_name=None, arguments={}),
            AgentStep(kind="final", final_answer="recovered"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router).run("g")

    assert result.outcome is LoopOutcome.completed
    assert result.steps[0].error == "unknown_tool"
    assert result.steps[1].error == "missing_tool_name"
    assert result.usage.tool_calls == 0


@pytest.mark.asyncio
async def test_failed_tool_becomes_an_observation_and_loop_continues():
    async def failing(_arguments: dict) -> ToolResult:
        return ToolResult(ok=False, summary="rate limited", error="rate_limit")

    router = ToolRouter([_tool("search", handler=failing)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="search", arguments={}),
            AgentStep(kind="final", final_answer="recovered after failure"),
        ]
    )
    result = await AgentLoop(brain=brain, router=router).run("g")

    assert result.outcome is LoopOutcome.completed
    assert result.steps[0].ok is False
    assert result.steps[0].error == "rate_limit"


@pytest.mark.asyncio
async def test_brain_exception_ends_loop_with_error_outcome():
    router = ToolRouter([_tool("search")])
    result = await AgentLoop(brain=BoomBrain(), router=router).run("g")

    assert result.outcome is LoopOutcome.error
    assert result.error == "brain exploded"


# --- observation truncation & compaction --------------------------------


@pytest.mark.asyncio
async def test_observation_is_truncated_to_the_limit():
    async def chatty(_arguments: dict) -> ToolResult:
        return ToolResult(ok=True, summary="x" * 5000)

    router = ToolRouter([_tool("search", handler=chatty)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="search", arguments={}),
            AgentStep(kind="final", final_answer="done"),
        ]
    )
    result = await AgentLoop(
        brain=brain, router=router, limits=LoopLimits(max_observation_chars=200)
    ).run("g")

    assert len(result.steps[0].observation) == 200
    assert result.steps[0].observation.endswith("…")


def test_compact_elides_the_middle_of_a_long_transcript():
    transcript = [f"line {i}" for i in range(100)]
    compacted = _compact(transcript, limit=10)

    assert len(compacted) == 10
    assert compacted[0] == "line 0"
    assert compacted[-1] == "line 99"
    assert "elided" in compacted[1]


# --- persistence & LLM brain --------------------------------------------


@pytest.mark.asyncio
async def test_loop_records_tool_calls_to_the_trace_tables(make_store):
    repo = await make_store().research_repository()
    router = ToolRouter([_tool("paper_search", permission=PermissionLevel.network_read)])
    brain = ScriptedBrain(
        steps=[
            AgentStep(kind="tool_call", tool_name="paper_search", arguments={"q": "rag"}),
            AgentStep(kind="final", final_answer="done"),
        ]
    )
    result = await AgentLoop(
        brain=brain,
        router=router,
        repository=repo,
        task_id="task_loop",
        project_id="proj_loop",
    ).run("survey RAG")

    assert result.outcome is LoopOutcome.completed
    calls = await repo.list_tool_calls("task_loop")
    assert [c.tool_name for c in calls] == ["paper_search"]
    observations = await repo.list_tool_observations(calls[0].id)
    assert observations[0].status.value == "ok"


@pytest.mark.asyncio
async def test_llm_agent_brain_finishes_with_a_mock_model():
    from athena.llm_factory import MockLLM

    router = ToolRouter([_tool("search")])
    result = await AgentLoop(brain=LLMAgentBrain(MockLLM()), router=router).run("survey RAG")

    # MockLLM replies in prose, not JSON -> parsed as a final answer.
    assert result.outcome is LoopOutcome.completed
    assert result.final_answer
