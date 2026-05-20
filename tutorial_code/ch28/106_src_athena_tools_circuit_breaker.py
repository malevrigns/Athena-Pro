"""轻量级断路器,专为外部工具调用设计"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Awaitable, TypeVar

from athena.observability import logger

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"          # 正常,请求都放过
    OPEN = "open"              # 熔断,直接走 fallback
    HALF_OPEN = "half_open"    # 试探性放一两个请求看是否恢复


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5                       # 连续失败几次熔断
    recovery_timeout_sec: float = 30                 # 熔断后多久试探一次
    half_open_max_calls: int = 1                     # 试探阶段允许几个 call
    
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0
    half_open_calls: int = 0
    _lock: asyncio.Lock = None
    
    def __post_init__(self):
        self._lock = asyncio.Lock()
    
    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args,
        fallback: Callable[..., Awaitable[T]] | None = None,
        **kwargs,
    ) -> T:
        async with self._lock:
            # 检查熔断状态
            if self.state == CircuitState.OPEN:
                if time.monotonic() - self.opened_at > self.recovery_timeout_sec:
                    logger.info("circuit_half_open", name=self.name)
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    logger.debug("circuit_short_circuit", name=self.name)
                    if fallback:
                        return await fallback(*args, **kwargs)
                    raise RuntimeError(f"Circuit {self.name} is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    if fallback:
                        return await fallback(*args, **kwargs)
                    raise RuntimeError(f"Circuit {self.name} half-open quota exceeded")
                self.half_open_calls += 1
        
        # 真正调用
        try:
            result = await fn(*args, **kwargs)
            async with self._lock:
                # 成功 → 复位
                if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                    logger.info("circuit_closed", name=self.name)
                self.state = CircuitState.CLOSED
                self.consecutive_failures = 0
            return result
        except Exception as e:
            async with self._lock:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.opened_at = time.monotonic()
                    logger.warning(
                        "circuit_opened",
                        name=self.name,
                        consecutive_failures=self.consecutive_failures,
                        error=str(e),
                    )
            if fallback:
                return await fallback()
            raise


# 全局单例
tavily_breaker = CircuitBreaker(name="tavily")