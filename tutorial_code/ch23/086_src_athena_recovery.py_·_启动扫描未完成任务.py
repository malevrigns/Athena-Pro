"""启动时找出未完成的研究任务,恢复执行。"""
from __future__ import annotations

from athena.graph.builders import build_main_graph
from athena.observability import logger
from athena.store.checkpointer import get_checkpointer


async def recover_pending_tasks(max_recover: int = 50) -> int:
    """扫描所有未走到 END 的 thread,触发恢复执行。返回恢复的任务数。"""
    checkpointer = await get_checkpointer()
    graph = await build_main_graph()
    
    recovered = 0
    pool = checkpointer.conn
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # 找出最新 checkpoint 不在 END 的 thread
            await cur.execute("""
                SELECT thread_id, MAX(checkpoint_id) AS last_ckpt
                FROM checkpoints
                GROUP BY thread_id
                HAVING NOT BOOL_OR(metadata->'writes' ? '__end__')
                LIMIT %s
            """, (max_recover,))
            pending = [row[0] async for row in cur]
    
    for thread_id in pending:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await graph.aget_state(config)
        
        if snapshot.next:                          # 还没跑完
            logger.info("recovering_task", thread_id=thread_id, next_node=snapshot.next)
            # 传 None 表示"从断点继续",不传新输入
            await graph.ainvoke(None, config=config)
            recovered += 1
    
    logger.info("recovery_done", recovered=recovered, total_pending=len(pending))
    return recovered