from __future__ import annotations

import asyncio
import random
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def async_retry(attempts: int = 3, base_delay: float = 0.1, max_delay: float = 2.0):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt == attempts:
                        break
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay = delay * (0.7 + random.random() * 0.6)
                    await asyncio.sleep(delay)
            assert last_error is not None
            raise last_error
        return wrapper
    return decorator
