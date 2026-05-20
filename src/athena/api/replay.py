from __future__ import annotations

from dataclasses import dataclass, field

from athena.schemas import StreamEvent


@dataclass
class ReplayStore:
    events: dict[str, list[StreamEvent]] = field(default_factory=dict)

    def append(self, event: StreamEvent) -> None:
        self.events.setdefault(event.task_id, []).append(event)

    def list(self, task_id: str, after_index: int = 0) -> list[StreamEvent]:
        return self.events.get(task_id, [])[after_index:]

    def compact(self, task_id: str, keep_last: int = 500) -> None:
        if task_id in self.events:
            self.events[task_id] = self.events[task_id][-keep_last:]
