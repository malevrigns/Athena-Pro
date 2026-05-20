"""
反馈收集器:用户点 👍/👎 时被调用。
不直接抽取 anti-pattern(那是 async background task 做的),
只负责存 raw feedback。
"""
from __future__ import annotations
import asyncio
import structlog
from athena.memory.schemas import Feedback
from athena.memory.store import save_feedback
from athena.memory.extractor import schedule_extraction

logger = structlog.get_logger()


async def collect_feedback(
    task_id: str,
    rating: str,                       # "up" | "down"
    comment: str = "",
    user_id: str | None = None,
) -> str:
    """
    保存反馈到 DB,并对 'down' 的反馈触发后台抽取。
    返回 feedback_id。
    """
    from athena.store.tasks import get_task
    
    # 从 task 表拿到 question + final_report
    task = await get_task(task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    
    feedback = Feedback(
        task_id=task_id,
        user_id=user_id,
        rating=rating,
        comment=comment,
        question=task.question,
        final_report=task.final_report or "",
    )
    
    await save_feedback(feedback)
    logger.info("feedback_saved",
                feedback_id=feedback.feedback_id,
                rating=rating,
                task_id=task_id)
    
    # 只对 down 触发抽取(up 不需要"教训")
    if rating == "down":
        # 不 await · fire-and-forget,API 立刻返回
        asyncio.create_task(_safe_extract(feedback.feedback_id))
    
    return feedback.feedback_id


async def _safe_extract(feedback_id: str) -> None:
    """后台执行,失败不影响 API 响应"""
    try:
        await schedule_extraction(feedback_id)
    except Exception as e:
        logger.exception("extraction_failed",
                         feedback_id=feedback_id,
                         error=str(e))