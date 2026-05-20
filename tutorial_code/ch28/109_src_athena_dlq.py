"""失败任务转入 Dead Letter Queue,等人工排查"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from athena.observability import logger
from athena.store.models import DeadLetterTask


async def send_to_dlq(
    task_id: str,
    failure_stage: str,
    error_type: str,
    error_message: str,
    state_snapshot: dict,
    db: AsyncSession,
) -> None:
    """把失败任务存到 DLQ 表。"""
    row = DeadLetterTask(
        task_id=task_id,
        failure_stage=failure_stage,                  # "planner" / "researcher" / "writer" ...
        error_type=error_type,
        error_message=error_message[:2000],
        state_snapshot_json=state_snapshot,
        failed_at=datetime.now(timezone.utc),
        retry_count=0,
        status="pending_review",
    )
    db.add(row)
    await db.commit()
    
    logger.error(
        "task_sent_to_dlq",
        task_id=task_id,
        stage=failure_stage,
        error_type=error_type,
    )


async def retry_dlq_task(task_id: str, graph, db: AsyncSession) -> bool:
    """从 DLQ 重试一个任务。返回是否成功。"""
    row = await db.get(DeadLetterTask, task_id)
    if not row or row.retry_count >= 3:
        return False
    
    row.retry_count += 1
    row.status = "retrying"
    await db.commit()
    
    try:
        config = {"configurable": {"thread_id": task_id}}
        await graph.ainvoke(None, config=config)              # 从最新 checkpoint 继续
        row.status = "recovered"
        await db.commit()
        return True
    except Exception as e:
        row.status = "failed_again"
        row.error_message = str(e)[:2000]
        await db.commit()
        return False