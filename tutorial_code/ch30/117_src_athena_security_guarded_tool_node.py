"""带权限守门的 ToolNode 替代品"""
from __future__ import annotations
from typing import Any, Sequence

from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.types import interrupt

from athena.observability import logger
from athena.security.permissions import (
    PermissionEngine, PermissionRequest, Decision,
)


class GuardedToolNode:
    """
    包装一组工具:每次执行前过权限引擎。
    Ask 决策 → 通过 interrupt() 等待用户审批。
    Deny 决策 → 返回错误 ToolMessage,不执行。
    Allow 决策 → 正常执行。
    """
    
    def __init__(
        self,
        tools: Sequence[BaseTool],
        engine: PermissionEngine,
    ):
        self.tools_by_name = {t.name: t for t in tools}
        self.engine = engine
    
    def __call__(self, state: dict) -> dict:
        """LangGraph 节点入口。state["messages"][-1] 应为带 tool_calls 的 AIMessage。"""
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}
        
        session_id = state.get("session_id") or state.get("task_id", "unknown")
        budget_remaining = state.get("cost_ledger", {}).get("budget_usd", 1) - \
                          state.get("cost_ledger", {}).get("spent_usd", 0)
        
        out_messages = []
        for call in last.tool_calls:
            tool_name = call["name"]
            tool_input = call["args"]
            
            req = PermissionRequest(
                tool_name=tool_name,
                tool_input=tool_input,
                session_id=session_id,
                budget_remaining_usd=budget_remaining,
            )
            result = self.engine.check(req)
            
            # ---- DENY ----
            if result.decision == Decision.DENY:
                logger.warning("tool_call_denied", tool=tool_name, rule=result.matched_rule)
                out_messages.append(ToolMessage(
                    content=f"⛔ 此操作被权限策略拒绝({result.matched_rule}):{result.reason}",
                    tool_call_id=call["id"],
                    name=tool_name,
                    status="error",
                ))
                continue
            
            # ---- ASK ----
            if result.decision == Decision.ASK:
                # 把决策权交给用户。interrupt 会暂停图,前端弹窗,用户选择 → resume
                user_decision = interrupt({
                    "type": "permission_request",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "risk_summary": result.risk_summary,
                    "rule": result.matched_rule,
                    "options": result.ask_options,
                })
                
                # user_decision 期待格式: {"choice": "approve_once" | "approve_session" | "deny", ...}
                choice = (user_decision or {}).get("choice", "deny")
                
                if choice == "deny":
                    out_messages.append(ToolMessage(
                        content="❌ 用户拒绝了此操作",
                        tool_call_id=call["id"],
                        name=tool_name,
                        status="error",
                    ))
                    continue
                
                if choice == "approve_session":
                    self.engine.remember_approval(req, scope="approve_session")
                # approve_once 不记住,继续执行(走到下面 Allow 的逻辑)
            
            # ---- ALLOW(或 ASK 后 approved) ----
            tool = self.tools_by_name.get(tool_name)
            if not tool:
                out_messages.append(ToolMessage(
                    content=f"❌ 未知工具:{tool_name}",
                    tool_call_id=call["id"],
                    name=tool_name,
                    status="error",
                ))
                continue
            
            try:
                tool_result = tool.invoke(tool_input)
                out_messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=call["id"],
                    name=tool_name,
                ))
            except Exception as e:
                logger.exception("tool_execution_failed", tool=tool_name)
                out_messages.append(ToolMessage(
                    content=f"工具执行错误:{type(e).__name__}: {e}",
                    tool_call_id=call["id"],
                    name=tool_name,
                    status="error",
                ))
        
        return {"messages": out_messages}