from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable

from athena.schemas import StreamEvent


@dataclass
class EventBus:
    """Per-task event bus used by SSE and the durable replay path.

    The bus keeps a bounded in-memory replay buffer so late subscribers get recent events
    immediately, and forwards every published event to an optional persistence hook so that
    SQLite (or any other store) keeps the full history. The bus is single-process and the runtime
    target is single-user, so no inter-process broadcast is needed.
    """

    replay_size: int = 1000
    _queues: dict[str, set[asyncio.Queue[StreamEvent]]] = field(default_factory=lambda: defaultdict(set))
    _replay: dict[str, deque[StreamEvent]] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=1000)))
    _seq: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    persistence_hook: Callable[[StreamEvent, int], Awaitable[None]] | None = None

    async def publish(self, event: StreamEvent) -> None:
        self._replay[event.task_id].append(event)
        self._seq[event.task_id] += 1
        seq = self._seq[event.task_id]
        if self.persistence_hook is not None:
            try:
                await self.persistence_hook(event, seq)
            except Exception:
                # Never let persistence failure break the live stream.
                pass
        for queue in list(self._queues[event.task_id]):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest from this queue and retry once.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    pass

    async def subscribe(self, task_id: str, replay: bool = True) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=512)
        self._queues[task_id].add(queue)
        try:
            if replay:
                for event in list(self._replay.get(task_id, [])):
                    yield event
            while True:
                yield await queue.get()
        finally:
            self._queues[task_id].discard(queue)

    def recent(self, task_id: str) -> list[StreamEvent]:
        return list(self._replay.get(task_id, []))

    def seed_from_history(self, task_id: str, events: list[StreamEvent]) -> None:
        """Pre-fill the replay deque from a persisted history so SSE subscribers can resume."""
        if not events:
            return
        deque_ = self._replay[task_id]
        for event in events[-self.replay_size:]:
            deque_.append(event)
        self._seq[task_id] = max(self._seq[task_id], len(events))


bus = EventBus()
