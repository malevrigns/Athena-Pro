"""Citation verification CRUD.

Citations themselves are part of the FinalReport JSON, this endpoint persists
the human (or future LLM) decision: pass / reject / flag / replaced.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from athena.persistence import get_store
from athena.runtime import runtime_store


router = APIRouter(prefix="/v1/research", tags=["citations"])


class VerifyRequest(BaseModel):
    status: Literal["pass", "reject", "flag", "replaced"]
    comment: str = ""
    decided_by: str = "human"


class CitationDecision(BaseModel):
    citation_n: int
    status: str
    comment: str = ""
    decided_by: str = "human"
    decided_at: str


class CitationListItem(BaseModel):
    number: int
    title: str
    url: str
    quote: str = ""
    decision: CitationDecision | None = None


@router.get("/{task_id}/citations")
async def list_citations(task_id: str):
    state = await runtime_store.get(task_id)
    if not state:
        raise HTTPException(404, "task not found")
    citations = state.final_report.citations if state.final_report else []
    decisions = {d["citation_n"]: d for d in await get_store().fetch_citation_verifications(task_id)}
    items: list[CitationListItem] = []
    for c in citations:
        d = decisions.get(c.number)
        items.append(CitationListItem(
            number=c.number,
            title=c.title,
            url=c.url,
            quote=c.quote or "",
            decision=CitationDecision(**d) if d else None,
        ))
    summary = {
        "total": len(items),
        "pass": sum(1 for i in items if i.decision and i.decision.status == "pass"),
        "reject": sum(1 for i in items if i.decision and i.decision.status == "reject"),
        "flag": sum(1 for i in items if i.decision and i.decision.status == "flag"),
        "replaced": sum(1 for i in items if i.decision and i.decision.status == "replaced"),
        "pending": sum(1 for i in items if not i.decision),
    }
    return {"items": [i.model_dump() for i in items], "summary": summary}


@router.post("/{task_id}/citations/{citation_n}/verify")
async def verify_citation(task_id: str, citation_n: int, body: VerifyRequest):
    state = await runtime_store.get(task_id)
    if not state:
        raise HTTPException(404, "task not found")
    if not state.final_report or citation_n not in {c.number for c in state.final_report.citations}:
        raise HTTPException(404, "citation not found in report")
    await get_store().upsert_citation_verification(
        task_id, citation_n, body.status, body.comment, body.decided_by,
    )
    return {"task_id": task_id, "citation_n": citation_n, "status": body.status}
