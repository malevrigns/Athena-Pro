"""任务启动时调用,从向量库捞相关 anti-pattern 注入 prompt"""
from __future__ import annotations
from datetime import datetime
import structlog
from athena.memory.schemas import MemoryQuery
from athena.memory.store import find_similar_patterns, save_anti_pattern

logger = structlog.get_logger()


async def inject_memory_into_prompt(question: str) -> str:
    """
    Planner 启动前调用,返回一段要拼到 system prompt 的"教训提醒"文本。
    检索不到时返回空串。
    """
    hits = await find_similar_patterns(question, top_k=3, min_similarity=0.65)
    
    if not hits:
        return ""
    
    # 标记 hit
    for hit in hits:
        hit.pattern.hit_count += 1
        hit.pattern.last_hit_at = datetime.utcnow()
        await save_anti_pattern(hit.pattern)
    
    # 格式化为 prompt 片段
    lines = ["\n## ⚠️ 历史教训(必须遵守)\n",
             "处理过类似任务时,曾出现过以下问题。本次请避免:\n"]
    for i, hit in enumerate(hits, 1):
        sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[hit.pattern.severity]
        lines.append(f"{i}. {sev_icon} **{hit.pattern.failure_mode}**")
        lines.append(f"   → 改进:{hit.pattern.correction}")
        lines.append("")
    
    injected = "\n".join(lines)
    logger.info("memory_injected",
                question_preview=question[:60],
                n_patterns=len(hits))
    return injected