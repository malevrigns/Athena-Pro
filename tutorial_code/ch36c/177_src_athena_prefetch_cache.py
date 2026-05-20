"""
双层缓存:
- 内存 LRU(同进程内瞬时命中)
- Redis(跨进程 / 跨 worker 共享)
TTL 设 5 分钟,跟 prompt cache 一致。
"""
from __future__ import annotations
import json
import hashlib
from cachetools import TTLCache
import redis.asyncio as redis

# 内存层 · 单进程,超快
_memory_cache: TTLCache = TTLCache(maxsize=1024, ttl=300)


class PrefetchCache:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=False)
    
    @staticmethod
    def _search_key(task_id: str, topic_id: str, query: str) -> str:
        q_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        return f"prefetch:search:{task_id}:{topic_id}:{q_hash}"
    
    @staticmethod
    def _fetch_key(task_id: str, url: str) -> str:
        u_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"prefetch:fetch:{task_id}:{u_hash}"
    
    async def set_search(
        self, task_id: str, topic_id: str, query: str, results: list
    ) -> None:
        key = self._search_key(task_id, topic_id, query)
        value = json.dumps(results, ensure_ascii=False).encode()
        _memory_cache[key] = value
        await self._redis.setex(key, 300, value)         # 5 分钟 TTL
    
    async def get_search(
        self, task_id: str, topic_id: str, query: str
    ) -> list | None:
        key = self._search_key(task_id, topic_id, query)
        # 先内存,miss 再 redis
        value = _memory_cache.get(key)
        if value is None:
            value = await self._redis.get(key)
            if value is not None:
                _memory_cache[key] = value
        return json.loads(value) if value else None
    
    async def set_fetch(self, task_id: str, url: str, content: str) -> None:
        key = self._fetch_key(task_id, url)
        _memory_cache[key] = content.encode()
        await self._redis.setex(key, 300, content)
    
    async def get_fetch(self, task_id: str, url: str) -> str | None:
        key = self._fetch_key(task_id, url)
        value = _memory_cache.get(key)
        if value is None:
            value = await self._redis.get(key)
            if value is not None:
                _memory_cache[key] = value
        return value.decode() if isinstance(value, bytes) else value
    
    async def invalidate_task(self, task_id: str) -> None:
        """删除一个 task 的所有 prefetch 缓存(用户拒绝 plan 时调)"""
        # 内存层用 prefix 扫描(LRU 不支持 SCAN,只能遍历)
        keys_to_del = [k for k in _memory_cache if task_id in k]
        for k in keys_to_del:
            _memory_cache.pop(k, None)
        
        # Redis 用 SCAN 找 prefix 匹配
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor,
                match=f"prefetch:*:{task_id}:*",
                count=100,
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break


# 全局单例
prefetch_cache = PrefetchCache(redis_url="redis://localhost:6379")