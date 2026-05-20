# 1. State
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class MyState(TypedDict):
    messages: Annotated[list, add_messages]
    custom_field: str

# 2. 节点
def node_a(state: MyState):
    return {"messages": [...], "custom_field": "..."}

# 3. 建图
builder = StateGraph(MyState)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)
graph = builder.compile()

# 跑
result = graph.invoke({"messages": [...], "custom_field": ""})