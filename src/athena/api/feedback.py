from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from athena.memory.store import Feedback, MemoryStore
from athena.runtime import runtime_store

router = APIRouter(prefix='/v1/feedback', tags=['feedback'])
store = MemoryStore()


class FeedbackRequest(BaseModel):
    task_id: str
    rating: int = Field(ge=-1, le=1)
    comment: str = ''


@router.post('')
async def post_feedback(body: FeedbackRequest):
    state = runtime_store.get(body.task_id)
    if not state:
        raise HTTPException(404, 'task not found')
    report = state.final_report.markdown if state.final_report else ''
    feedback = Feedback(task_id=body.task_id, rating=body.rating, comment=body.comment, final_report=report)
    store.add_feedback(feedback)
    return feedback.model_dump(mode='json')
