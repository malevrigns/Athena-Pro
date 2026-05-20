"""三级权限引擎 · Athena · 借鉴 Claude Code 设计"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from athena.observability import logger


class Decision(Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class PermissionRequest:
    """一次工具调用请求 - 喂给规则引擎判断。"""
    tool_name: str
    tool_input: dict[str, Any]
    session_id: str
    user_id: str | None = None
    
    # 上下文(给规则用),按需注入
    budget_remaining_usd: float = 1.0
    
    def get_command(self) -> str | None:
        """如果是 bash 工具,提取命令字符串。"""
        if self.tool_name == "bash":
            return self.tool_input.get("command", "")
        return None
    
    def get_path(self) -> str | None:
        if self.tool_name in ("file_write", "file_read"):
            return self.tool_input.get("path", "")
        return None
    
    def get_url(self) -> str | None:
        if self.tool_name == "http_request":
            return self.tool_input.get("url", "")
        return None


@dataclass
class PermissionResult:
    decision: Decision
    matched_rule: str
    reason: str = ""
    risk_summary: str = ""
    # 如果 decision=ASK,前端用这些字段渲染弹窗
    ask_options: list[str] = field(default_factory=lambda: [
        "approve_once",         # 仅这一次
        "approve_session",      # 整个会话都批准这个模式
        "deny",                 # 拒绝
    ])


# ============ 规则匹配器 ============
class Rule:
    """单条规则,从 YAML 加载。"""
    def __init__(self, raw: dict):
        self.name = raw["name"]
        self.decision = Decision(raw["decision"])
        self.matches = raw.get("matches", {})
        self.reason = raw.get("reason", "")
        self.risk_summary = raw.get("risk_summary", "")
        # 可选:budget 条件
        self.only_when_budget_below = raw.get("only_when_budget_remaining_below")
        # 预编译正则
        self._cmd_re = re.compile(self.matches["command_pattern"]) if "command_pattern" in self.matches else None
        self._path_re = re.compile(self.matches["path_pattern"]) if "path_pattern" in self.matches else None
        self._url_re = re.compile(self.matches["url_pattern"]) if "url_pattern" in self.matches else None
    
    def matches_request(self, req: PermissionRequest) -> bool:
        """这条规则是否匹配请求。"""
        m = self.matches
        # tool 名(可能是 tool 或 tool_in)
        if "tool" in m and req.tool_name != m["tool"]:
            return False
        if "tool_in" in m and req.tool_name not in m["tool_in"]:
            return False
        # 命令模式
        if self._cmd_re:
            cmd = req.get_command() or ""
            if not self._cmd_re.search(cmd):
                return False
        # 路径模式
        if self._path_re:
            path = req.get_path() or ""
            if not self._path_re.search(path):
                return False
        # URL 模式
        if self._url_re:
            url = req.get_url() or ""
            if not self._url_re.search(url):
                return False
        # 预算条件
        if self.only_when_budget_below is not None:
            if req.budget_remaining_usd >= self.only_when_budget_below:
                return False                          # 预算充足,这条规则不激活
        return True


# ============ 会话级"批准记忆" ============
@dataclass
class SessionPermissionCache:
    """记住用户在会话中说过的"approve_session" - 避免重复问。"""
    session_id: str
    approved_patterns: set[str] = field(default_factory=set)
    
    @staticmethod
    def make_key(req: PermissionRequest) -> str:
        """把请求归一化为一个 key,用于会话级缓存。"""
        # 关键设计:不是按"完整命令"缓存,而是按"工具 + 关键模式"
        # 例如 "bash:git_pull" 而不是 "bash:git pull origin main"
        cmd = req.get_command() or ""
        if cmd:
            # 取首词 + 二级词(git pull / npm install)
            tokens = cmd.split()
            kind = " ".join(tokens[:2]) if len(tokens) > 1 else (tokens[0] if tokens else "")
            return f"{req.tool_name}:{kind}"
        return f"{req.tool_name}"
    
    def has_session_approval(self, req: PermissionRequest) -> bool:
        return self.make_key(req) in self.approved_patterns
    
    def remember_session_approval(self, req: PermissionRequest) -> None:
        self.approved_patterns.add(self.make_key(req))


# ============ 主引擎 ============
class PermissionEngine:
    """三级权限引擎主入口。"""
    
    def __init__(self, rules_path: Path):
        with open(rules_path) as f:
            data = yaml.safe_load(f)
        self.rules = [Rule(r) for r in data["rules"]]
        self.default_decision = Decision(data.get("default", "ask"))
        self._session_caches: dict[str, SessionPermissionCache] = {}
    
    def _get_session_cache(self, session_id: str) -> SessionPermissionCache:
        if session_id not in self._session_caches:
            self._session_caches[session_id] = SessionPermissionCache(session_id)
        return self._session_caches[session_id]
    
    def check(self, req: PermissionRequest) -> PermissionResult:
        """对一次工具调用做权限判断。这是热路径,要快。"""
        # 1) 检查会话缓存
        cache = self._get_session_cache(req.session_id)
        if cache.has_session_approval(req):
            logger.debug("permission_session_approved", tool=req.tool_name)
            return PermissionResult(
                decision=Decision.ALLOW,
                matched_rule="",
                reason="用户本会话已批准此模式",
            )
        
        # 2) 按顺序匹配规则
        for rule in self.rules:
            if rule.matches_request(req):
                logger.info(
                    "permission_decision",
                    rule=rule.name,
                    decision=rule.decision.value,
                    tool=req.tool_name,
                )
                return PermissionResult(
                    decision=rule.decision,
                    matched_rule=rule.name,
                    reason=rule.reason,
                    risk_summary=rule.risk_summary,
                )
        
        # 3) 默认决定
        logger.info("permission_default", decision=self.default_decision.value, tool=req.tool_name)
        return PermissionResult(
            decision=self.default_decision,
            matched_rule="",
            reason="无匹配规则,使用默认",
        )
    
    def remember_approval(self, req: PermissionRequest, scope: str) -> None:
        """用户做出"approve_session"决策后调用,把模式存到会话缓存。"""
        if scope == "approve_session":
            self._get_session_cache(req.session_id).remember_session_approval(req)
            logger.info(
                "permission_session_remembered",
                session_id=req.session_id,
                pattern=SessionPermissionCache.make_key(req),
            )