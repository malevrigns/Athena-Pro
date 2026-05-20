from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from athena.persistence.audit_log import list_audit_items


router = APIRouter(prefix="/v1/audit", tags=["audit"])


class AuditEvent(BaseModel):
    id: str
    type: Literal["plan_review", "citation_verification"]
    title: str
    status: str
    actor: str
    task_id: str
    route: str
    created_at: str
    detail: str = ""


@router.get("/events")
async def list_events(limit: int = Query(20, ge=1, le=100)) -> dict[str, object]:
    items = [AuditEvent.model_validate(item).model_dump() for item in await list_audit_items(limit)]
    return {"items": items, "total": len(items)}
