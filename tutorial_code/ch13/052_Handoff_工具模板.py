from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

def create_handoff_tool(*, agent_name: str, description: str = None):
    """工厂函数:为指定的 agent 生成一个交接工具。"""
    name = f"transfer_to_{agent_name}"
    
    @tool(name, description=description or f"把任务交给 {agent_name}。")
    def handoff(
        task_description: Annotated[str, "下一个 agent 需要做什么"],
        state: Annotated[dict, InjectedState],            # ← 注入当前 state
        tool_call_id: Annotated[str, InjectedToolCallId], # ← 注入当前工具调用 ID
    ) -> Command:
        return Command(
            goto=agent_name,
            graph=Command.PARENT,    # 跳出当前 agent(子图),进入兄弟 agent
            update={
                "messages": state["messages"] + [ToolMessage(
                    content=f"已交接给 {agent_name},任务:{task_description}",
                    name=name,
                    tool_call_id=tool_call_id,
                )],
            },
        )
    return handoff

# 用法:给每个 agent 准备它能交接的对象
transfer_to_writer = create_handoff_tool(agent_name="writer")
transfer_to_reviewer = create_handoff_tool(agent_name="reviewer")