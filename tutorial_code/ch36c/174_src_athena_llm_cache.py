"""
Prompt caching 封装。
两个目标:
  1. 让"系统 prompt + skill 注入 + memory 注入"这种"半静态"内容能被缓存
  2. 自动管理缓存边界(cache_control 标记的位置)
"""
from __future__ import annotations
from typing import Any
import structlog

logger = structlog.get_logger()


def mark_cacheable(content: str, ttl: str = "5m") -> dict:
    """
    把一段文本包装成 Anthropic API 可缓存的 content block。
    
    Args:
        content: prompt 文本
        ttl: "5m"(默认)或 "1h"(超长 TTL 选项,稍贵但断流后还在)
    
    Returns:
        Anthropic API messages 里的 content block dict
    """
    return {
        "type": "text",
        "text": content,
        "cache_control": {"type": "ephemeral", "ttl": ttl},
    }


def build_cached_system_prompt(
    base_prompt: str,
    skill_content: str = "",
    memory_content: str = "",
) -> list[dict]:
    """
    把 system prompt 切成"稳定大块 + 动态小尾"两段:
    - 第一段标记缓存:base_prompt + skill(变动少)
    - 第二段不缓存:memory(每次注入不同 anti-pattern)
    
    这样 cache key 只依赖第一段,memory 变了不破坏缓存。
    """
    blocks: list[dict] = []
    
    # 大块,标记缓存
    stable_part = base_prompt
    if skill_content:
        stable_part += "\n\n" + skill_content
    blocks.append(mark_cacheable(stable_part, ttl="5m"))
    
    # 动态小尾,不缓存
    if memory_content:
        blocks.append({
            "type": "text",
            "text": memory_content,
            # 故意不加 cache_control
        })
    
    return blocks


def estimate_savings(stable_tokens: int, n_calls: int) -> dict:
    """
    估算这次任务能省多少 token / 钱。
    给开发者调试用 + Grafana 展示用。
    """
    # 第一次:写缓存,25% 溢价
    # 第 2..N 次:读缓存,10% 价格
    full_price_tokens = stable_tokens * n_calls
    
    cached_tokens = (
        stable_tokens * 1.25 +              # 第一次写
        stable_tokens * 0.10 * (n_calls - 1) # 后续读
    )
    
    saved = full_price_tokens - cached_tokens
    saved_pct = saved / full_price_tokens if full_price_tokens > 0 else 0
    
    return {
        "stable_tokens": stable_tokens,
        "n_calls": n_calls,
        "full_price_tokens": int(full_price_tokens),
        "cached_tokens": int(cached_tokens),
        "saved_tokens": int(saved),
        "saved_pct": round(saved_pct, 3),
    }