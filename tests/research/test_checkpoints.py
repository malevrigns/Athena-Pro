"""Tests for durable, blocking review checkpoints (roadmap section 11)."""

from __future__ import annotations

import asyncio

import pytest

from athena.research.domain import (
    CheckpointStatus,
    CheckpointType,
    ResearchProject,
    ReviewDecision,
)
from athena.research.runtime import CheckpointService, checkpoint_approval_handler
from athena.research.runtime.loop import ApprovalAsk
from athena.research.governance.policy import ApprovalDecision


async def _project(repo) -> ResearchProject:
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    return project


@pytest.mark.asyncio
async def test_open_persists_a_pending_checkpoint(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)

    checkpoint = await service.open(
        task_id="task_1",
        project_id=project.id,
        checkpoint_type=CheckpointType.plan_review,
        title="Approve plan",
        content={"steps": ["search"]},
    )

    stored = await repo.get_checkpoint(checkpoint.id)
    assert stored is not None
    assert stored.status is CheckpointStatus.pending
    assert await service.list_pending(project.id) == [stored]


@pytest.mark.asyncio
async def test_wait_blocks_until_the_checkpoint_is_resolved(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)
    checkpoint = await service.open(
        task_id="task_1",
        project_id=project.id,
        checkpoint_type=CheckpointType.plan_review,
        title="Approve plan",
    )

    waiter = asyncio.create_task(service.wait(checkpoint.id))
    await asyncio.sleep(0.02)
    assert not waiter.done()  # genuinely blocked, not a fake gate

    await service.resolve(checkpoint.id, ReviewDecision.approved, comment="ok")
    decided = await asyncio.wait_for(waiter, timeout=1)
    assert decided.status is CheckpointStatus.decided
    assert decided.decision is ReviewDecision.approved
    assert decided.comment == "ok"
    assert decided.decided_at is not None
    assert await service.list_pending(project.id) == []


@pytest.mark.asyncio
async def test_wait_returns_immediately_for_an_already_decided_checkpoint(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)
    checkpoint = await service.open(
        task_id="task_1",
        project_id=project.id,
        checkpoint_type=CheckpointType.citation_audit,
        title="Audit",
    )
    await service.resolve(checkpoint.id, ReviewDecision.rejected)

    decided = await asyncio.wait_for(service.wait(checkpoint.id), timeout=1)
    assert decided.decision is ReviewDecision.rejected


@pytest.mark.asyncio
async def test_resolve_is_idempotent_and_rejects_unknown_ids(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)
    checkpoint = await service.open(
        task_id="task_1",
        project_id=project.id,
        checkpoint_type=CheckpointType.plan_review,
        title="Approve plan",
    )

    first = await service.resolve(checkpoint.id, ReviewDecision.approved)
    second = await service.resolve(checkpoint.id, ReviewDecision.rejected)
    assert second.decision is first.decision is ReviewDecision.approved

    with pytest.raises(KeyError):
        await service.resolve("ckpt_missing", ReviewDecision.approved)


@pytest.mark.asyncio
async def test_checkpoint_approval_handler_blocks_a_tool_until_approved(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)
    handler = checkpoint_approval_handler(service, task_id="task_1", project_id=project.id)
    ask = ApprovalAsk(
        tool_name="run_local_command",
        arguments={"cmd": "pytest"},
        decision=ApprovalDecision(required=True, reason="local command", risk_level="high"),
    )

    decision_task = asyncio.create_task(handler(ask))
    await asyncio.sleep(0.02)
    assert not decision_task.done()

    pending = await service.list_pending(project.id)
    assert len(pending) == 1
    assert pending[0].checkpoint_type is CheckpointType.experiment_execution
    await service.resolve(pending[0].id, ReviewDecision.approved)

    assert await asyncio.wait_for(decision_task, timeout=1) is True


@pytest.mark.asyncio
async def test_checkpoint_approval_handler_returns_false_on_rejection(make_store):
    repo = await make_store().research_repository()
    project = await _project(repo)
    service = CheckpointService(repo)
    handler = checkpoint_approval_handler(service, task_id="task_1", project_id=project.id)
    ask = ApprovalAsk(
        tool_name="write_repo",
        arguments={},
        decision=ApprovalDecision(required=True, reason="repo write", risk_level="medium"),
    )

    decision_task = asyncio.create_task(handler(ask))
    await asyncio.sleep(0.02)
    pending = await service.list_pending(project.id)
    await service.resolve(pending[0].id, ReviewDecision.rejected)

    assert await asyncio.wait_for(decision_task, timeout=1) is False
