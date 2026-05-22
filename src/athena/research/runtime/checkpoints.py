"""Durable, genuinely-blocking review checkpoints (roadmap section 11).

The risk the roadmap calls out (section 12.4) is a *fake* human-in-the-loop:
a UI approve button while the backend keeps running. `CheckpointService`
prevents that — `wait()` does not return until a decision is persisted to the
`review_checkpoints` table and delivered.

Two layers cooperate:
- the table is the durable record (survives a restart);
- an in-process `asyncio.Event` per checkpoint is the live wake-up.

`checkpoint_approval_handler` plugs this into the agent loop: a tool that needs
approval opens a checkpoint and the loop blocks on it.
"""

from __future__ import annotations

import asyncio

from athena.research.domain import (
    CheckpointStatus,
    CheckpointType,
    ReviewCheckpoint,
    ReviewDecision,
)
from athena.research.persistence import ResearchRepository
from athena.research.tools import utcnow

from .loop import ApprovalAsk, ApprovalHandler


class CheckpointService:
    """Creates, blocks on, and resolves durable review checkpoints."""

    def __init__(self, repository: ResearchRepository) -> None:
        self._repository = repository
        self._events: dict[str, asyncio.Event] = {}

    async def open(
        self,
        *,
        task_id: str,
        project_id: str,
        checkpoint_type: CheckpointType,
        title: str,
        content: dict | None = None,
    ) -> ReviewCheckpoint:
        """Persist a new pending checkpoint and arm its wake-up event."""
        checkpoint = ReviewCheckpoint(
            task_id=task_id,
            project_id=project_id,
            checkpoint_type=checkpoint_type,
            title=title,
            content=content or {},
        )
        await self._repository.create_checkpoint(checkpoint)
        self._events[checkpoint.id] = asyncio.Event()
        return checkpoint

    async def wait(self, checkpoint_id: str, *, timeout: float | None = None) -> ReviewCheckpoint:
        """Block until the checkpoint is decided, then return its final state.

        If the checkpoint was already decided (e.g. resolved before the waiter
        arrived, or after a restart) this returns immediately.
        """
        event = self._events.get(checkpoint_id)
        if event is None:
            checkpoint = await self._repository.get_checkpoint(checkpoint_id)
            if checkpoint is None:
                raise KeyError(f"unknown checkpoint: {checkpoint_id}")
            if checkpoint.status is CheckpointStatus.decided:
                return checkpoint
            # A pending checkpoint with no live event (e.g. restored after a
            # restart) — arm an event and wait on it.
            event = self._events.setdefault(checkpoint_id, asyncio.Event())

        if timeout is not None:
            await asyncio.wait_for(event.wait(), timeout)
        else:
            await event.wait()

        checkpoint = await self._repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:  # pragma: no cover - resolve() writes before set()
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        return checkpoint

    async def resolve(
        self,
        checkpoint_id: str,
        decision: ReviewDecision,
        *,
        comment: str | None = None,
    ) -> ReviewCheckpoint:
        """Record a human decision and wake any waiter. Idempotent."""
        checkpoint = await self._repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        if checkpoint.status is CheckpointStatus.decided:
            return checkpoint

        decided = checkpoint.model_copy(
            update={
                "status": CheckpointStatus.decided,
                "decision": decision,
                "comment": comment,
                "decided_at": utcnow(),
            }
        )
        await self._repository.upsert_checkpoint(decided)
        event = self._events.get(checkpoint_id)
        if event is not None:
            event.set()
        return decided

    async def get(self, checkpoint_id: str) -> ReviewCheckpoint | None:
        return await self._repository.get_checkpoint(checkpoint_id)

    async def list_for_project(self, project_id: str) -> list[ReviewCheckpoint]:
        return await self._repository.list_project_checkpoints(project_id)

    async def list_pending(self, project_id: str) -> list[ReviewCheckpoint]:
        checkpoints = await self._repository.list_project_checkpoints(project_id)
        return [c for c in checkpoints if c.status is CheckpointStatus.pending]


def checkpoint_approval_handler(
    service: CheckpointService,
    *,
    task_id: str,
    project_id: str,
) -> ApprovalHandler:
    """Build an agent-loop approval handler backed by durable checkpoints.

    Each tool call that requires approval opens an `experiment_execution`
    checkpoint; the loop blocks on it until a human approves or rejects.
    """

    async def handler(ask: ApprovalAsk) -> bool:
        checkpoint = await service.open(
            task_id=task_id,
            project_id=project_id,
            checkpoint_type=CheckpointType.experiment_execution,
            title=f"Approve tool call: {ask.tool_name}",
            content={
                "tool": ask.tool_name,
                "arguments": ask.arguments,
                "risk_level": ask.decision.risk_level,
                "reason": ask.decision.reason,
            },
        )
        decided = await service.wait(checkpoint.id)
        return decided.decision is ReviewDecision.approved

    return handler


__all__ = [
    "CheckpointService",
    "checkpoint_approval_handler",
]
