from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncIterator
from uuid import uuid4

from athena.config import get_settings
from athena.events import bus
from athena.graph.main_graph import run_research_graph
from athena.observability import logger
from athena.persistence import get_store
from athena.schemas import StreamEvent, TaskSnapshot, TaskStatus
from athena.state import ResearchState


@dataclass
class RuntimeStore:
    states: dict[str, ResearchState] = field(default_factory=dict)
    tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    abort_flags: dict[str, asyncio.Event] = field(default_factory=dict)
    started: bool = False

    async def ensure_started(self) -> None:
        if self.started:
            return
        store = get_store()
        await store.connect()
        # Mark anything left non-terminal from a previous process as failed.
        orphan_count = await store.mark_orphan_tasks_failed()
        if orphan_count:
            logger.info("runtime.orphan_tasks_marked_failed", extra={"count": orphan_count})
        # Wire the bus persistence hook so every event is durable.
        bus.persistence_hook = store.append_event
        self.started = True

    def create_state(self, question: str, user_id: str = "demo-user") -> ResearchState:
        task_id = f"task_{uuid4().hex[:10]}"
        state = ResearchState(task_id=task_id, question=question, user_id=user_id)
        self.states[task_id] = state
        self.abort_flags[task_id] = asyncio.Event()
        state.add_event("created", node="api", question=question)
        return state

    async def run_background(self, state: ResearchState) -> None:
        store = get_store()
        try:
            for event in state.events:
                await bus.publish(event)
            await store.upsert_task(state)
            timeout = get_settings().hard_timeout_sec
            async def _run() -> None:
                async for _event in run_research_graph(state):
                    if self.abort_flags[state.task_id].is_set():
                        state.status = TaskStatus.CANCELLED
                        await bus.publish(state.add_event("cancelled", node="runtime", reason="user interrupt"))
                        break
                    await store.upsert_task(state)
            try:
                await asyncio.wait_for(_run(), timeout=timeout)
            except asyncio.TimeoutError:
                state.status = TaskStatus.FAILED
                await bus.publish(state.add_event("error", node="runtime", error=f"hard timeout after {timeout}s"))
        except Exception as exc:  # noqa: BLE001
            state.status = TaskStatus.FAILED
            logger.exception("runtime.task_failed", extra={"task_id": state.task_id})
            await bus.publish(state.add_event("error", node="runtime", error=str(exc)))
        finally:
            await store.upsert_task(state)

    async def start(self, question: str, user_id: str = "demo-user") -> ResearchState:
        await self.ensure_started()
        state = self.create_state(question, user_id=user_id)
        task = asyncio.create_task(self.run_background(state), name=f"athena:{state.task_id}")
        self.tasks[state.task_id] = task
        return state

    def interrupt(self, task_id: str) -> bool:
        flag = self.abort_flags.get(task_id)
        if not flag:
            return False
        flag.set()
        return True

    async def get(self, task_id: str) -> ResearchState | None:
        state = self.states.get(task_id)
        if state is not None:
            return state
        # Try rehydrating from SQLite so cross-process replays / history pages keep working.
        return await self._rehydrate(task_id)

    async def _rehydrate(self, task_id: str) -> ResearchState | None:
        store = get_store()
        row = await store.fetch_task_json(task_id)
        if not row:
            return None
        try:
            payload = json.loads(row["state_json"])
            snapshot = payload.get("snapshot", {})
        except Exception:
            return None
        state = ResearchState(
            task_id=row["task_id"],
            question=row["question"],
            user_id=row["user_id"],
            status=TaskStatus(row["status"]),
        )
        # Populate higher-level fields from snapshot for read-only access.
        from athena.schemas import FinalReport, Finding, QualityScore, ResearchPlan, TokenUsage
        if snapshot.get("plan"):
            state.plan = ResearchPlan.model_validate(snapshot["plan"])
        state.findings = [Finding.model_validate(f) for f in snapshot.get("findings", [])]
        if snapshot.get("final_report"):
            state.final_report = FinalReport.model_validate(snapshot["final_report"])
        if snapshot.get("quality"):
            state.quality = QualityScore.model_validate(snapshot["quality"])
        state.token_usage = [TokenUsage.model_validate(u) for u in payload.get("token_usage", [])]
        state.errors = list(payload.get("errors", []))
        state.metadata = payload.get("metadata", {})
        # Re-attach events from store and seed bus replay.
        events = await store.fetch_events(task_id)
        state.events = events
        bus.seed_from_history(task_id, events)
        self.states[task_id] = state
        return state

    async def snapshots(self) -> list[TaskSnapshot]:
        store = get_store()
        rows = await store.list_tasks(limit=100)
        result: list[TaskSnapshot] = []
        for row in rows:
            try:
                payload = json.loads(row["state_json"])
                snapshot = TaskSnapshot.model_validate(payload["snapshot"])
                result.append(snapshot)
            except Exception:
                continue
        return result

    async def stream(self, task_id: str, replay: bool = True) -> AsyncIterator[StreamEvent]:
        await self.ensure_started()
        # Ensure replay history is loaded from disk if this is a cold start.
        if task_id not in self.states:
            await self._rehydrate(task_id)
        async for event in bus.subscribe(task_id, replay=replay):
            yield event


runtime_store = RuntimeStore()
