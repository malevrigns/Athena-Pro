from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, TypedDict

from athena.state import ResearchState


class ResearchGraphState(TypedDict):
    """LangGraph envelope for the mutable Athena runtime state.

    Agent nodes currently operate on `ResearchState` directly. Keeping that
    object behind one stable graph key avoids duplicating every state field in
    LangGraph and prevents orchestration code from owning domain-state syncing.
    """

    runtime: ResearchState


RuntimeNode: TypeAlias = Callable[[ResearchState], Awaitable[ResearchState | None]]
GraphNode: TypeAlias = Callable[[ResearchGraphState], Awaitable[ResearchGraphState]]


def graph_state(runtime: ResearchState) -> ResearchGraphState:
    return {"runtime": runtime}


def runtime_node(node: RuntimeNode) -> GraphNode:
    async def wrapped(state: ResearchGraphState) -> ResearchGraphState:
        runtime = state["runtime"]
        result = await node(runtime)
        return graph_state(result if isinstance(result, ResearchState) else runtime)

    wrapped.__name__ = getattr(node, "__name__", "runtime_node")
    return wrapped
