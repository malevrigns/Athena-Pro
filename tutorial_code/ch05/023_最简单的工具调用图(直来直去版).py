from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# 1. 工具
@tool
def get_weather(city: str) -> str:
    """获取某城市天气。"""
    return f"{city}:晴,15°C"

# 2. State
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# 3. LLM(带工具)
tools = [get_weather]
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

# 4. 节点
def llm_node(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

tool_node = ToolNode(tools, handle_tool_errors=True)

# 5. 建图(单次:LLM → 工具 → LLM → END)
builder = StateGraph(State)
builder.add_node("llm", llm_node)
builder.add_node("tools", tool_node)
builder.add_edge(START, "llm")
builder.add_edge("llm", "tools")
builder.add_edge("tools", "llm")    # 工具结果送回 LLM
builder.add_edge("llm", END)        # ⚠️ 但这样会无限循环或报错

graph = builder.compile()