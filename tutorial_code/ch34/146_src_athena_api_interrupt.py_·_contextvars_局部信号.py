"""中断正在跑的 Graph"""
from __future__ import annotations
import asyncio
from contextvars import ContextVar
from typing import Optional

# 跟随当前任务的"取消令牌"
_abort_token: ContextVar[Optional[asyncio.Event]] = ContextVar(
    "abort_token", default=None
)


def get_abort_token() -> asyncio.Event | None:
    return _abort_token.get()


def set_abort_token(event: asyncio.Event) -> None:
    _abort_token.set(event)


class TaskAborted(Exception):
    """Agent 被用户中断。"""
    pass


def check_abort() -> None:
    """节点函数可以在任意位置调这个,被中断则抛 TaskAborted。"""
    event = _abort_token.get()
    if event is not None and event.is_set():
        raise TaskAborted("user requested abort")