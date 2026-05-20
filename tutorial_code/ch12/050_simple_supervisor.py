from typing import Literal, TypedDict
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class State(MessagesState):
    next: str   # 主管的最新决定,便于调试

# ---------- 工人节点 ----------
def researcher(state) -> Command[Literal["supervisor"]]:
    """研究员:做研究然后回到 supervisor。"""
    result = llm.invoke([
        {"role": "system", "content": "你是研究员,简要列举 3 个关于此问题的事实。"},
        *state["messages"]
    ])
    return Command(
        goto="supervisor",
        update={"messages": [HumanMessage(content=result.content, name="researcher")]}
    )

def writer(state) -> Command[Literal["supervisor"]]:
    """写作员。"""
    result = llm.invoke([
        {"role": "system", "content": "你是写作员,基于已有信息写一段简短文章。"},
        *state["messages"]
    ])
    return Command(
        goto="supervisor",
        update={"messages": [HumanMessage(content=result.content, name="writer")]}
    )

# ---------- 主管 ----------
class Router(TypedDict):
    """主管的输出格式:选下一个工人,或 FINISH。"""
    next: Literal["researcher", "writer", "FINISH"]

system_prompt = """你是团队主管。工人:researcher(研究员)、writer(写作员)。
- 如果还没有事实,派 researcher
- 如果有事实但没文章,派 writer
- 如果文章已写完,FINISH
回复时返回结构化的 next 字段。"""

def supervisor(state) -> Command[Literal["researcher", "writer", "__end__"]]:
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    decision = llm.with_structured_output(Router).invoke(messages)
    goto = decision["next"]
    if goto == "FINISH":
        goto = END
    return Command(goto=goto, update={"next": goto})

# ---------- 建图 ----------
builder = StateGraph(State)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", researcher)
builder.add_node("writer", writer)
builder.add_edge(START, "supervisor")
# 注意:没有任何 add_edge 在节点之间!Command 已经处理了所有路由

graph = builder.compile()

# ---------- 跑 ----------
for chunk in graph.stream(
    {"messages": [HumanMessage(content="介绍下 LangGraph 是什么")]},
    stream_mode="updates"
):
    for node, update in chunk.items():
        print(f"\n=== {node} ===")
        for m in update.get("messages", [])[-1:]:
            print(f"[{getattr(m, 'name', '?')}] {m.content[:200]}")