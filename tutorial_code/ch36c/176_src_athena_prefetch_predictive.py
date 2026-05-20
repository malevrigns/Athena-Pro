"""
Predictive prefetch:Planner 输出 plan 后立刻预跑 Researcher。
- 用户审核期间不阻塞
- 结果存 prefetch_cache
- 用户批准时 Researcher 优先读 cache,miss 才真跑
"""
from __future__ import annotations
import asyncio
from typing import Any
import structlog
from athena.prefetch.cache import prefetch_cache
from athena.tools.web_search import web_search
from athena.tools.fetcher import fetch_url

logger = structlog.get_logger()


# 全局 task 注册表,key = task_id,value = list of asyncio.Task
_prefetch_tasks: dict[str, list[asyncio.Task]] = {}


async def start_prefetch(task_id: str, research_plan: list[dict]) -> None:
    """
    Planner 输出 plan 后立刻调用,后台预跑每个 topic 的搜索。
    不 await,这是 fire-and-forget。
    """
    if task_id in _prefetch_tasks:
        logger.warning("prefetch_already_running", task_id=task_id)
        return
    
    tasks = []
    for topic in research_plan:
        # 每个 topic 一个独立协程
        task = asyncio.create_task(
            _prefetch_one_topic(task_id, topic),
            name=f"prefetch:{task_id}:{topic['id']}",
        )
        tasks.append(task)
    
    _prefetch_tasks[task_id] = tasks
    logger.info("prefetch_started", task_id=task_id, n_topics=len(research_plan))


async def _prefetch_one_topic(task_id: str, topic: dict) -> None:
    """单个 topic 的预跑。失败静默,不影响其他 topic。"""
    try:
        # 用 LLM 生成 1-2 个搜索 query(简化版:直接用 topic + why)
        query = f"{topic['topic']} {topic.get('why', '')[:60]}"
        
        # 1. 搜索
        search_results = await web_search(query)
        await prefetch_cache.set_search(task_id, topic["id"], query, search_results)
        
        # 2. 抓前 2 个 URL
        urls = [r["url"] for r in search_results[:2] if "url" in r]
        for url in urls:
            content = await fetch_url(url)
            await prefetch_cache.set_fetch(task_id, url, content)
        
        logger.info(
            "prefetch_topic_done",
            task_id=task_id,
            topic_id=topic["id"],
            n_urls=len(urls),
        )
    except asyncio.CancelledError:
        # 用户拒绝 plan,我们 cancel 了所有 prefetch task
        logger.info("prefetch_cancelled", task_id=task_id, topic_id=topic["id"])
        raise
    except Exception as e:
        # 任何错误静默吞掉,prefetch 失败不能影响主流程
        logger.exception(
            "prefetch_topic_failed",
            task_id=task_id, topic_id=topic["id"],
            error=str(e),
        )


async def cancel_prefetch(task_id: str) -> None:
    """用户拒绝 plan 时调用。取消所有正在跑的 prefetch。"""
    tasks = _prefetch_tasks.pop(task_id, [])
    for t in tasks:
        t.cancel()
    
    # 等所有 cancel 生效(防止资源泄漏)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # 顺手清掉 cache(避免修改后的 plan 误用旧 cache)
    await prefetch_cache.invalidate_task(task_id)
    
    logger.info("prefetch_cancelled_all", task_id=task_id, n_cancelled=len(tasks))


async def commit_prefetch(task_id: str) -> None:
    """用户批准 plan 时调用。停止收 cancel 信号(让进行中的 prefetch 跑完)"""
    # 不 cancel,让它们自然完成。它们的结果还在 cache 里。
    _prefetch_tasks.pop(task_id, None)
    logger.info("prefetch_committed", task_id=task_id)