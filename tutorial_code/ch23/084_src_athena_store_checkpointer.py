"""
异步 Postgres Checkpointer · 全局单例 · 支持连接池
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from athena.config import settings
from athena.observability import logger

# ===================== 全局连接池 =====================
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_init_lock = asyncio.Lock()


async def get_pool() -> AsyncConnectionPool:
    """获取全局连接池,首次访问时初始化。"""
    global _pool
    if _pool is None:
        async with _init_lock:
            if _pool is None:                       # double-checked locking
                _pool = AsyncConnectionPool(
                    conninfo=settings.postgres_dsn,
                    min_size=settings.pg_pool_min_size,        # 默认 5
                    max_size=settings.pg_pool_max_size,        # 默认 20
                    kwargs={
                        "autocommit": True,                    # checkpointer 要求
                        "prepare_threshold": 0,                # PgBouncer 兼容
                    },
                    open=False,
                )
                await _pool.open()
                logger.info(
                    "pg_pool_opened",
                    min_size=settings.pg_pool_min_size,
                    max_size=settings.pg_pool_max_size,
                )
    return _pool


async def get_checkpointer() -> AsyncPostgresSaver:
    """获取全局 checkpointer 单例。"""
    global _checkpointer
    if _checkpointer is None:
        async with _init_lock:
            if _checkpointer is None:
                pool = await get_pool()
                _checkpointer = AsyncPostgresSaver(pool)
                await _checkpointer.setup()         # 自动 migration,首次启动建表
                logger.info("checkpointer_initialized")
    return _checkpointer


async def close_resources() -> None:
    """优雅停机:关池子。"""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("pg_pool_closed")


@asynccontextmanager
async def lifespan_pg() -> AsyncGenerator[None, None]:
    """FastAPI lifespan 钩子。"""
    await get_checkpointer()                        # 启动时预热
    try:
        yield
    finally:
        await close_resources()