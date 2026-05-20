from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable

from athena.observability import logger
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
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    persistence_hook: Callable[[StreamEvent, int], Awaitable[None]] | None = None

    async def publish(self, event: StreamEvent) -> None:
        async with self._lock:
            self._seq[event.task_id] += 1
            seq = self._seq[event.task_id]
            event.seq = seq
            if self.persistence_hook is not None:
                try:
                    await self.persistence_hook(event, seq)
                except Exception:
                    logger.exception("event.persistence_failed task_id=%s seq=%s", event.task_id, seq)
                    raise
            self._replay[event.task_id].append(event)
            queues = list(self._queues[event.task_id])
        for queue in queues:
            self._put_latest(queue, event)

    @staticmethod
    def _put_latest(queue: asyncio.Queue[StreamEvent], event: StreamEvent) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except Exception:
                logger.exception("event.queue_overflow task_id=%s seq=%s", event.task_id, event.seq)

    async def subscribe(
        self,
        task_id: str,
        replay: bool = True,
        after_seq: int = 0,
    ) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=512)
        async with self._lock:
            replay_events = [
                event for event in list(self._replay.get(task_id, []))
                if replay and event.seq > after_seq
            ]
            self._queues[task_id].add(queue)
        try:
            for event in replay_events:
                yield event
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._queues[task_id].discard(queue)

    def recent(self, task_id: str) -> list[StreamEvent]:
        return list(self._replay.get(task_id, []))

    def seed_from_history(self, task_id: str, events: list[StreamEvent]) -> None:
        """Pre-fill the replay deque from a persisted history so SSE subscribers can resume."""
        if not events:
            return
        deque_ = self._replay[task_id]
        for index, event in enumerate(events[-self.replay_size:], start=1):
            if not event.seq:
                event.seq = index
            deque_.append(event)
        self._seq[task_id] = max(self._seq[task_id], max(event.seq for event in events))


bus = EventBus()
