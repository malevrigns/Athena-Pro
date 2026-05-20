from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# 工具
@tool
def get_weather(city: str) -> str:
    """获取城市天气。"""
    return f"{city}:晴,15°C,空气质量良好"

@tool
def calculator(expression: str) -> str:
    """计算数学表达式。"""
    return str(eval(expression))

tools = [get_weather, calculator]
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

# State
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# 节点
def llm_node(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

# 建图
builder = StateGraph(State)
builder.add_node("llm", llm_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))

builder.add_edge(START, "llm")
# 关键:条件边
builder.add_conditional_edges(
    "llm",
    tools_condition,    # 内置路由函数:有 tool_calls 就去 "tools",否则 END
)
builder.add_edge("tools", "llm")   # 工具执行完回到 LLM

graph = builder.compile()