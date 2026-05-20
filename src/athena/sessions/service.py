from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Session:
    id: str
    user_id: str
    title: str
    task_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionService:
    sessions: dict[str, Session] = field(default_factory=dict)

    def create(self, user_id: str, title: str) -> Session:
        session = Session(id=f"sess_{uuid4().hex[:10]}", user_id=user_id, title=title)
        self.sessions[session.id] = session
        return session

    def attach_task(self, session_id: str, task_id: str) -> None:
        self.sessions[session_id].task_ids.append(task_id)

    def list_for_user(self, user_id: str) -> list[Session]:
        return [s for s in self.sessions.values() if s.user_id == user_id]
