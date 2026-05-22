"""In-process human-in-the-loop gates.

Plan review genuinely blocks the research graph: `plan_review_apply_node`
awaits a `ReviewGate` until `POST /v1/research/{id}/review` delivers a
decision. Single-process / single-user, so a plain in-memory dict of
`asyncio.Event`s is enough — no external broker needed. If the process
restarts mid-wait the task becomes an orphan and is marked failed on boot.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from athena.schemas import ReviewDecision


@dataclass
class ReviewGate:
    """A one-shot channel: the graph awaits `event`, the API fills `decision`."""

    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: ReviewDecision | None = None


_gates: dict[str, ReviewGate] = {}


def open_gate(task_id: str) -> ReviewGate:
    """Register a review gate for a task before its graph starts running."""
    gate = ReviewGate()
    _gates[task_id] = gate
    return gate


def get_gate(task_id: str) -> ReviewGate | None:
    return _gates.get(task_id)


def submit_decision(task_id: str, decision: ReviewDecision) -> bool:
    """Deliver a human decision to a waiting task.

    Returns False when no gate is open (the task is not awaiting review).
    """
    gate = _gates.get(task_id)
    if gate is None:
        return False
    gate.decision = decision
    gate.event.set()
    return True


def close_gate(task_id: str) -> None:
    """Drop a task's gate once its run has finished."""
    _gates.pop(task_id, None)
