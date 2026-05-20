"""Subagent 类型注册 + 派发"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Awaitable

from athena.observability import logger


@dataclass
class SubagentSpec:
    """Subagent 类型定义"""
    name: str
    system_prompt: str
    tools_factory: Callable[[], list]      # 返回该 subagent 可用的工具列表
    model: str = "gpt-4o-mini"             # 默认用便宜模型
    max_iterations: int = 10


# ===== 内置 Subagent 类型 =====
def _web_researcher_tools():
    from athena.tools.search import web_search
    from athena.tools.web_fetch import web_fetch
    return [web_search, web_fetch]


def _fact_checker_tools():
    from athena.tools.search import web_search
    return [web_search]                    # FactChecker 只能搜索,不能写不能跑代码


def _code_runner_tools():
    from athena.tools.sandbox_tools import python_repl
    return [python_repl]                   # 只允许 Python REPL,不允许 bash


def _doc_reader_tools():
    from athena.tools.web_fetch import web_fetch
    from athena.tools.pdf_reader import pdf_reader
    return [web_fetch, pdf_reader]