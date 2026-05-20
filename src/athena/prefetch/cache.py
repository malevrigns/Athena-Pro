from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass
class CacheItem(Generic[T]):
    value: T
    expires_at: float
    hits: int = 0


@dataclass
class TTLCache(Generic[T]):
    max_size: int = 256
    ttl_sec: float = 300.0
    _items: OrderedDict[str, CacheItem[T]] = field(default_factory=OrderedDict)

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        now = time.time()
        if not item:
            return None
        if item.expires_at < now:
            self._items.pop(key, None)
            return None
        item.hits += 1
        self._items.move_to_end(key)
        return item.value

    def set(self, key: str, value: T, ttl_sec: float | None = None) -> None:
        while len(self._items) >= self.max_size:
            self._items.popitem(last=False)
        self._items[key] = CacheItem(value=value, expires_at=time.time() + (ttl_sec or self.ttl_sec))

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def clear_expired(self) -> int:
        now = time.time()
        expired = [key for key, item in self._items.items() if item.expires_at < now]
        for key in expired:
            self._items.pop(key, None)
        return len(expired)

    def stats(self) -> dict[str, int | float]:
        return {
            'size': len(self._items),
            'max_size': self.max_size,
            'ttl_sec': self.ttl_sec,
            'hits': sum(item.hits for item in self._items.values()),
        }


prefetch_cache: TTLCache[object] = TTLCache(max_size=512, ttl_sec=300.0)
