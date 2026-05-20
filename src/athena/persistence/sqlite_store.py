from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from athena.config import get_settings
from athena.schemas import StreamEvent, TaskStatus
from athena.state import ResearchState


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    question     TEXT NOT NULL,
    status       TEXT NOT NULL,
    state_json   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    type         TEXT NOT NULL,
    node         TEXT,
    payload_json TEXT NOT NULL,
    ts           TEXT NOT NULL,
    UNIQUE(task_id, seq)
);

CREATE TABLE IF NOT EXISTS citation_verifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    citation_n  INTEGER NOT NULL,
    status      TEXT NOT NULL,            -- 'pass' | 'reject' | 'flag' | 'replaced'
    comment     TEXT,
    decided_by  TEXT,
    decided_at  TEXT NOT NULL,
    UNIQUE(task_id, citation_n)
);

CREATE TABLE IF NOT EXISTS knowledge_collections (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    icon        TEXT,
    color       TEXT,
    description TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id            TEXT PRIMARY KEY,
    collection_id TEXT,
    name          TEXT NOT NULL,
    summary       TEXT,
    type          TEXT,
    source        TEXT,
    tags_csv      TEXT,
    usage_count   INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'pending', -- 'verified' | 'pending'
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cite_task ON citation_verifications(task_id);
CREATE INDEX IF NOT EXISTS idx_kn_items_coll ON knowledge_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_kn_items_updated ON knowledge_items(updated_at DESC);
"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_to_json(state: ResearchState) -> str:
    snapshot = state.to_snapshot()
    payload = {
        "snapshot": snapshot.model_dump(mode="json"),
        "metadata": _safe_metadata(state.metadata),
        "errors": list(state.errors),
        "messages": list(state.messages),
        "token_usage": [u.model_dump(mode="json") for u in state.token_usage],
        "permission_requests": [p.model_dump(mode="json") for p in state.permission_requests],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _failed_snapshot_json(state_json: str) -> str:
    payload = json.loads(state_json)
    payload.setdefault("snapshot", {})["status"] = TaskStatus.FAILED.value
    return json.dumps(payload, ensure_ascii=False, default=str)


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Strip non-serialisable runtime objects (like TokenLedger) before persisting."""
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "ledger":
            try:
                safe["ledger"] = value.snapshot()  # type: ignore[union-attr]
            except Exception:
                continue
        else:
            try:
                json.dumps(value, default=str)
                safe[key] = value
            except Exception:
                continue
    return safe


class SQLiteStore:
    """Async SQLite persistence for tasks and events.

    The store keeps a single connection guarded by an asyncio lock — fine for the single-user
    deployment target.  Switch to a connection pool if you ever fan out to multiple workers.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def upsert_task(self, state: ResearchState) -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            now = _iso_now()
            await self._conn.execute(
                """
                INSERT INTO tasks(task_id, user_id, question, status, state_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (
                    state.task_id,
                    state.user_id,
                    state.question,
                    state.status.value,
                    _state_to_json(state),
                    now,
                    now,
                ),
            )
            await self._conn.commit()

    async def append_event(self, event: StreamEvent, seq: int) -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            try:
                await self._conn.execute(
                    "INSERT INTO events(task_id, seq, type, node, payload_json, ts) VALUES(?, ?, ?, ?, ?, ?)",
                    (
                        event.task_id,
                        seq,
                        event.type,
                        event.node,
                        json.dumps(event.payload, ensure_ascii=False, default=str),
                        event.ts.isoformat(),
                    ),
                )
                await self._conn.commit()
            except aiosqlite.IntegrityError:
                # Duplicate seq — safe to ignore (we replay-on-restart)
                pass

    async def fetch_task_json(self, task_id: str) -> dict[str, Any] | None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT task_id, user_id, question, status, state_json, created_at, updated_at FROM tasks WHERE task_id = ?",
                (task_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if not row:
            return None
        return {
            "task_id": row[0],
            "user_id": row[1],
            "question": row[2],
            "status": row[3],
            "state_json": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    async def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT task_id, user_id, question, status, state_json, created_at, updated_at FROM tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            {
                "task_id": r[0],
                "user_id": r[1],
                "question": r[2],
                "status": r[3],
                "state_json": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    async def fetch_events(self, task_id: str) -> list[StreamEvent]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT seq, type, node, payload_json, ts FROM events WHERE task_id = ? ORDER BY seq ASC",
                (task_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        events: list[StreamEvent] = []
        for seq, type_, node, payload_json, ts in rows:
            events.append(
                StreamEvent(
                    seq=seq,
                    type=type_,
                    task_id=task_id,
                    node=node,
                    payload=json.loads(payload_json) if payload_json else {},
                    ts=datetime.fromisoformat(ts),
                )
            )
        return events

    # ----------- Citation verification -----------
    async def upsert_citation_verification(self, task_id: str, n: int, status: str, comment: str = "", decided_by: str = "human") -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO citation_verifications(task_id, citation_n, status, comment, decided_by, decided_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, citation_n) DO UPDATE SET
                    status = excluded.status,
                    comment = excluded.comment,
                    decided_by = excluded.decided_by,
                    decided_at = excluded.decided_at
                """,
                (task_id, n, status, comment, decided_by, _iso_now()),
            )
            await self._conn.commit()

    async def fetch_citation_verifications(self, task_id: str) -> list[dict[str, Any]]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT citation_n, status, comment, decided_by, decided_at FROM citation_verifications WHERE task_id = ?",
                (task_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            {"citation_n": r[0], "status": r[1], "comment": r[2], "decided_by": r[3], "decided_at": r[4]}
            for r in rows
        ]

    # ----------- Knowledge -----------
    async def list_knowledge_collections(self) -> list[dict[str, Any]]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "SELECT id, name, icon, color, description, created_at, updated_at FROM knowledge_collections ORDER BY updated_at DESC"
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            {"id": r[0], "name": r[1], "icon": r[2], "color": r[3], "description": r[4], "created_at": r[5], "updated_at": r[6]}
            for r in rows
        ]

    async def upsert_knowledge_collection(self, payload: dict[str, Any]) -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            now = _iso_now()
            await self._conn.execute(
                """
                INSERT INTO knowledge_collections(id, name, icon, color, description, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    icon = excluded.icon,
                    color = excluded.color,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (payload["id"], payload["name"], payload.get("icon"), payload.get("color"), payload.get("description"), now, now),
            )
            await self._conn.commit()

    async def list_knowledge_items(
        self, collection_id: str | None = None, search: str | None = None,
        status: str | None = None, limit: int = 100, offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        await self.connect()
        assert self._conn is not None
        where: list[str] = []
        args: list[Any] = []
        if collection_id:
            where.append("collection_id = ?")
            args.append(collection_id)
        if search:
            where.append("(name LIKE ? OR summary LIKE ? OR tags_csv LIKE ?)")
            args += [f"%{search}%"] * 3
        if status:
            where.append("status = ?")
            args.append(status)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        async with self._lock:
            cursor = await self._conn.execute(
                f"SELECT id, collection_id, name, summary, type, source, tags_csv, usage_count, status, created_at, updated_at "
                f"FROM knowledge_items{clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (*args, limit, offset),
            )
            rows = await cursor.fetchall()
            await cursor.close()
            count_cur = await self._conn.execute(f"SELECT COUNT(*) FROM knowledge_items{clause}", args)
            total = (await count_cur.fetchone())[0]
            await count_cur.close()
        items = [
            {
                "id": r[0], "collection_id": r[1], "name": r[2], "summary": r[3], "type": r[4],
                "source": r[5], "tags": (r[6] or "").split(",") if r[6] else [],
                "usage_count": r[7], "status": r[8], "created_at": r[9], "updated_at": r[10],
            } for r in rows
        ]
        return items, total

    async def upsert_knowledge_item(self, payload: dict[str, Any]) -> None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            now = _iso_now()
            tags_csv = ",".join(payload.get("tags") or [])
            await self._conn.execute(
                """
                INSERT INTO knowledge_items(id, collection_id, name, summary, type, source, tags_csv, usage_count, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    collection_id = excluded.collection_id,
                    name = excluded.name,
                    summary = excluded.summary,
                    type = excluded.type,
                    source = excluded.source,
                    tags_csv = excluded.tags_csv,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"], payload.get("collection_id"), payload["name"], payload.get("summary"),
                    payload.get("type"), payload.get("source"), tags_csv,
                    payload.get("usage_count", 0), payload.get("status", "pending"), now, now,
                ),
            )
            await self._conn.commit()

    async def verify_knowledge_item(self, item_id: str) -> bool:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "UPDATE knowledge_items SET status = ?, updated_at = ? WHERE id = ?",
                ("verified", _iso_now(), item_id),
            )
            await self._conn.commit()
            changed = cursor.rowcount
            await cursor.close()
        return bool(changed)

    async def delete_knowledge_item(self, item_id: str) -> bool:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cursor = await self._conn.execute(
                "DELETE FROM knowledge_items WHERE id = ?",
                (item_id,),
            )
            await self._conn.commit()
            changed = cursor.rowcount
            await cursor.close()
        return bool(changed)

    async def knowledge_overview(self) -> dict[str, Any]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            c = await self._conn.execute("SELECT COUNT(*), SUM(CASE WHEN status='verified' THEN 1 ELSE 0 END) FROM knowledge_items")
            row = await c.fetchone()
            await c.close()
            total, verified = (row[0] or 0, row[1] or 0)
            tag_cursor = await self._conn.execute("SELECT tags_csv FROM knowledge_items")
            tag_rows = await tag_cursor.fetchall()
            await tag_cursor.close()
        from collections import Counter
        counter: Counter[str] = Counter()
        for (csv,) in tag_rows:
            if not csv: continue
            for t in csv.split(","):
                if t.strip(): counter[t.strip()] += 1
        return {
            "total_items": total,
            "verified_items": verified,
            "verified_pct": round(verified / total * 100, 1) if total else 0.0,
            "hot_tags": [{"label": k, "count": v} for k, v in counter.most_common(10)],
            "active_tags": len(counter),
        }

    async def mark_orphan_tasks_failed(self) -> int:
        """Called at startup: any task left in a non-terminal status is marked failed so the UI
        does not show stale 'running' rows after a restart."""
        await self.connect()
        assert self._conn is not None
        terminal = {"done", "failed", "cancelled"}
        async with self._lock:
            cursor = await self._conn.execute("SELECT task_id, status, state_json FROM tasks")
            rows = await cursor.fetchall()
            await cursor.close()
            count = 0
            for task_id, status, state_json in rows:
                if status not in terminal:
                    updated_state_json = _failed_snapshot_json(state_json)
                    await self._conn.execute(
                        "UPDATE tasks SET status = ?, state_json = ?, updated_at = ? WHERE task_id = ?",
                        (TaskStatus.FAILED.value, updated_state_json, _iso_now(), task_id),
                    )
                    count += 1
            if count:
                await self._conn.commit()
        return count


_store: SQLiteStore | None = None


def get_store() -> SQLiteStore:
    global _store
    if _store is None:
        settings = get_settings()
        assert settings.sqlite_path is not None
        _store = SQLiteStore(settings.sqlite_path)
    return _store
