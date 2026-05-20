"""
Redis 缓存的薄封装。
"""
from __future__ import annotations
import logging
from typing import Any

import redis.asyncio as redis

from athena.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """全局唯一的异步 Redis 客户端。"""
    global _client
    if _client is None:
        _client = redis.from_url(
            _settings.db.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _client


async def cache_get(key: str) -> str | None:
    """读缓存。Redis 不可用时返回 None,不抛异常。"""
    try:
        return await get_redis().get(key)
    except redis.RedisError as e:
        logger.warning("cache.read_failed", extra={"key": key, "error": str(e)})
        return None


async def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> None:
    """写缓存。失败只 log,不影响主流程。"""
    try:
        await get_redis().setex(key, ttl_seconds, value)
    except redis.RedisError as e:
        logger.warning("cache.write_failed", extra={"key": key, "error": str(e)})


async def close_redis() -> None:
    """优雅关闭,FastAPI shutdown 调用。"""
    global _client
    if _client is not None:
        await _client.close()
        _client = None