from __future__ import annotations

from typing import AsyncIterator

from athena.agents.human_review import plan_review_node
from athena.agents.planner import planner_node
from athena.agents.quality import quality_gate_node
from athena.agents.researcher import researcher_node
from athena.agents.reviewer import reviewer_node
from athena.agents.supervisor import supervisor_node
from athena.agents.writer import writer_node
from athena.config import get_settings
from athena.events import bus
from athena.schemas import StreamEvent, TaskStatus
from athena.state import ResearchState


async def run_research_graph(state: ResearchState) -> AsyncIterator[StreamEvent]:
    """Top-level entry point used by the runtime.

    Tries the LangGraph backend when explicitly enabled; otherwise runs the iterative supervisor
    loop implemented below. Both paths publish StreamEvents on the bus and yield them so the SSE
    handler can forward each one to the browser.
    """
    settings = get_settings()
    if settings.use_langgraph:
        async for event in _run_langgraph_if_available(state):
            yield event
        return
    async for event in run_research_graph_without_langgraph(state):
        yield event


async def _run_langgraph_if_available(state: ResearchState) -> AsyncIterator[StreamEvent]:
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore
    except Exception:
        state.add_event("warning", node="graph", message="LangGraph not installed; fallback runtime used")
        async for event in run_research_graph_without_langgraph(state):
            yield event
        return
    builder = StateGraph(ResearchState)
    builder.add_node("planner", planner_node)
    builder.add_node("plan_review", plan_review_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("quality_gate", quality_gate_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("writer", writer_node)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "plan_review")
    builder.add_edge("plan_review", "supervisor")
    builder.add_edge("supervisor", "researcher")
    builder.add_edge("researcher", "quality_gate")
    builder.add_edge("quality_gate", "writer")
    builder.add_edge("writer", END)
    graph = builder.compile()
    result = await graph.ainvoke(state)
    result_state: ResearchState = result if isinstance(result, ResearchState) else state
    for event in result_state.events:
        await bus.publish(event)
        yield event


async def run_research_graph_without_langgraph(state: ResearchState) -> AsyncIterator[StreamEvent]:
    """Iterative supervisor loop.

    Order: planner → plan_review → (researcher → quality_gate → reviewer)* → writer
    The (...) block repeats until the quality threshold is hit or we run out of iterations,
    so failing reports auto-trigger follow-up research instead of shipping a half-baked draft.
    """
    settings = get_settings()
    cursor = 0

    async def _flush() -> AsyncIterator[StreamEvent]:
        nonlocal cursor
        while cursor < len(state.events):
            event = state.events[cursor]
            cursor += 1
            await bus.publish(event)
            yield event

    async def _run(node) -> AsyncIterator[StreamEvent]:
        await node(state)
        async for ev in _flush():
            yield ev

    # 1. planner
    async for ev in _run(planner_node):
        yield ev
    if state.status == TaskStatus.CANCELLED:
        return
    # 2. plan review
    async for ev in _run(plan_review_node):
        yield ev
    if state.status == TaskStatus.CANCELLED:
        return
    # 3. iterative research
    max_iters = max(1, settings.max_research_iterations)
    threshold = max(0.0, min(1.0, settings.quality_threshold))
    for iteration in range(1, max_iters + 1):
        state.metadata["research_iteration"] = iteration
        await supervisor_node(state)
        async for ev in _flush():
            yield ev
        async for ev in _run(researcher_node):
            yield ev
        async for ev in _run(quality_gate_node):
            yield ev
        if state.quality and state.quality.overall >= threshold:
            break
        if iteration == max_iters:
            break
        # Only invoke reviewer if we still have iterations left — otherwise we waste tokens.
        async for ev in _run(reviewer_node):
            yield ev
    # 4. writer
    async for ev in _run(writer_node):
        yield ev
