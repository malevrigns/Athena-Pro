from __future__ import annotations

from typing import AsyncIterator

from athena.agents.citation_review import citation_review_node
from athena.agents.human_review import plan_review_apply_node, plan_review_request_node
from athena.agents.planner import planner_node
from athena.agents.quality import quality_gate_node
from athena.agents.researcher import researcher_node
from athena.agents.reviewer import reviewer_node
from athena.agents.supervisor import supervisor_node
from athena.agents.writer import writer_node
from athena.config import get_settings
from athena.events import bus
from athena.graph.langgraph_adapter import ResearchGraphState, graph_state, runtime_node
from athena.schemas import StreamEvent, TaskStatus
from athena.state import ResearchState


async def run_research_graph(state: ResearchState) -> AsyncIterator[StreamEvent]:
    """Top-level entry point used by the runtime.

    LangGraph is the production orchestration backend. The hand-written runner
    below remains as a legacy/test fallback and is used only when
    ATHENA_USE_LANGGRAPH=false.
    """
    settings = get_settings()
    if settings.use_langgraph:
        async for event in _run_langgraph(state):
            yield event
        return
    async for event in run_research_graph_without_langgraph(state):
        yield event


async def _run_langgraph(state: ResearchState) -> AsyncIterator[StreamEvent]:
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore
    except Exception as exc:  # pragma: no cover - only hit in a misconfigured environment
        raise RuntimeError("LangGraph is required for production agent orchestration") from exc

    settings = get_settings()
    cursor = len(state.events)

    async def _flush() -> AsyncIterator[StreamEvent]:
        nonlocal cursor
        while cursor < len(state.events):
            event = state.events[cursor]
            cursor += 1
            await bus.publish(event)
            yield event

    async def iteration_start_node(state: ResearchState) -> ResearchState:
        current = int(state.metadata.get("research_iteration", 0) or 0)
        state.metadata["research_iteration"] = current + 1
        return state

    def after_quality(state: ResearchGraphState) -> str:
        runtime = state["runtime"]
        if runtime.status == TaskStatus.CANCELLED:
            return "cancelled"
        max_iters = max(1, settings.max_research_iterations)
        threshold = max(0.0, min(1.0, settings.quality_threshold))
        iteration = int(runtime.metadata.get("research_iteration", 1) or 1)
        if runtime.quality and runtime.quality.overall >= threshold:
            return "writer"
        if iteration >= max_iters:
            return "writer"
        return "reviewer"

    builder = StateGraph(ResearchGraphState)
    builder.add_node("planner", runtime_node(planner_node))
    builder.add_node("plan_review_request", runtime_node(plan_review_request_node))
    builder.add_node("plan_review_apply", runtime_node(plan_review_apply_node))
    builder.add_node("iteration_start", runtime_node(iteration_start_node))
    builder.add_node("supervisor", runtime_node(supervisor_node))
    builder.add_node("researcher", runtime_node(researcher_node))
    builder.add_node("quality_gate", runtime_node(quality_gate_node))
    builder.add_node("reviewer", runtime_node(reviewer_node))
    builder.add_node("writer", runtime_node(writer_node))
    builder.add_node("citation_review", runtime_node(citation_review_node))
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "plan_review_request")
    builder.add_edge("plan_review_request", "plan_review_apply")
    builder.add_edge("plan_review_apply", "iteration_start")
    builder.add_edge("iteration_start", "supervisor")
    builder.add_edge("supervisor", "researcher")
    builder.add_edge("researcher", "quality_gate")
    builder.add_conditional_edges(
        "quality_gate",
        after_quality,
        {
            "writer": "writer",
            "reviewer": "reviewer",
            "cancelled": END,
        },
    )
    builder.add_edge("reviewer", "iteration_start")
    builder.add_edge("writer", "citation_review")
    builder.add_edge("citation_review", END)
    graph = builder.compile()
    async for _ in graph.astream(graph_state(state), stream_mode="values"):
        async for event in _flush():
            yield event


async def run_research_graph_without_langgraph(state: ResearchState) -> AsyncIterator[StreamEvent]:
    """Iterative supervisor loop.

    Order: planner → plan_review → (researcher → quality_gate → reviewer)* → writer
    The (...) block repeats until the quality threshold is hit or we run out of iterations,
    so failing reports auto-trigger follow-up research instead of shipping a half-baked draft.
    """
    settings = get_settings()
    # Start past any pre-existing events so a resumed run only publishes the
    # new events it produces (and a fresh run never double-publishes `created`).
    cursor = len(state.events)

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
    # 2. plan review — emit the request (flushed to the client first), then
    #    block on plan_review_apply_node until the human approves, so research
    #    genuinely waits for sign-off instead of auto-running.
    async for ev in _run(plan_review_request_node):
        yield ev
    if state.status == TaskStatus.CANCELLED:
        return
    async for ev in _run(plan_review_apply_node):
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
    # 5. citation review — verifies report citations and emits the terminal `done`
    async for ev in _run(citation_review_node):
        yield ev
