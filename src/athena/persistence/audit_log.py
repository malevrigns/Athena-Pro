from __future__ import annotations

import json
from typing import Any

import aiosqlite

from athena.persistence import get_store


AuditItem = dict[str, Any]


async def list_audit_items(limit: int) -> list[AuditItem]:
    store = get_store()
    await store.connect()
    async with aiosqlite.connect(store.db_path) as conn:
        reviews = await _fetch_review_items(conn)
        citations = await _fetch_citation_items(conn)
    items = [*reviews, *citations]
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:limit]


async def _fetch_review_items(conn: aiosqlite.Connection) -> list[AuditItem]:
    cursor = await conn.execute("SELECT task_id, question, state_json, updated_at FROM tasks")
    rows = await cursor.fetchall()
    await cursor.close()
    return [_review_item(row) for row in rows if _review_decision(row[2])]


async def _fetch_citation_items(conn: aiosqlite.Connection) -> list[AuditItem]:
    cursor = await conn.execute(
        """
        SELECT c.task_id, t.question, c.citation_n, c.status, c.comment, c.decided_by, c.decided_at
        FROM citation_verifications c
        LEFT JOIN tasks t ON t.task_id = c.task_id
        """
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [_citation_item(row) for row in rows]


def _review_item(row: tuple[Any, ...]) -> AuditItem:
    task_id, question, state_json, updated_at = row
    decision = _review_decision(state_json)
    assert decision is not None
    approved = bool(decision.get("approved"))
    actor = str(decision.get("reviewer") or "human")
    return {
        "id": f"review:{task_id}",
        "type": "plan_review",
        "title": f"研究计划 - {question}",
        "status": "pass" if approved else "reject",
        "actor": actor,
        "task_id": task_id,
        "route": f"/workbench/{task_id}" if approved else "/plan-review",
        "created_at": str(decision.get("created_at") or updated_at),
        "detail": str(decision.get("comments") or ""),
    }


def _citation_item(row: tuple[Any, ...]) -> AuditItem:
    task_id, question, citation_n, status, comment, decided_by, decided_at = row
    return {
        "id": f"citation:{task_id}:{citation_n}",
        "type": "citation_verification",
        "title": f"引用验证 [{citation_n}] - {question or task_id}",
        "status": status,
        "actor": decided_by or "human",
        "task_id": task_id,
        "route": f"/workbench/{task_id}",
        "created_at": decided_at,
        "detail": comment or "",
    }


def _review_decision(state_json: str) -> dict[str, Any] | None:
    payload = json.loads(state_json)
    decision = payload.get("metadata", {}).get("review_decision")
    return decision if isinstance(decision, dict) else None
