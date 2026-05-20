from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from athena.runtime import runtime_store
from athena.schemas import TaskSnapshot, TaskStatus

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    snapshots = await runtime_store.snapshots()
    items = [_notification_for(snapshot) for snapshot in snapshots]
    active = [item for item in items if item is not None]
    active.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": active[:limit], "unread": len(active)}


def _notification_for(snapshot: TaskSnapshot) -> dict[str, Any] | None:
    if snapshot.status == TaskStatus.WAITING_REVIEW:
        return _build_notification(
            snapshot,
            "plan_review",
            "Plan review is waiting",
            "warning",
            "/plan-review",
        )
    if snapshot.status == TaskStatus.FAILED:
        return _build_notification(
            snapshot,
            "task_failed",
            "Research task failed",
            "error",
            f"/workbench/{snapshot.id}",
        )
    return None


def _build_notification(
    snapshot: TaskSnapshot,
    kind: str,
    title: str,
    level: str,
    route: str,
) -> dict[str, Any]:
    return {
        "id": f"{kind}:{snapshot.id}",
        "kind": kind,
        "title": title,
        "desc": snapshot.question,
        "level": level,
        "task_id": snapshot.id,
        "route": route,
        "created_at": snapshot.updated_at.isoformat(),
    }
