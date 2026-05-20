"""
把任务拆给多个 worker 并行,然后汇聚。
"""
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send


class State(TypedDict):
    topics: list[str]
    findings: Annotated[list[str], operator.add]


def dispatch(state):
    """把每个 topic 派给一个 worker 实例(并行)。"""
    return [Send("worker", {"topic": t}) for t in state["topics"]]


def worker(state):
    """单个 worker 处理一个 topic。"""
    return {"findings": [f"研究 {state['topic']} 的结果"]}


def aggregate(state):
    """所有 worker 完成后,汇聚结果。"""
    print(f"收集到 {len(state['findings'])} 条研究")
    return {}


builder = StateGraph(State)
builder.add_node("worker", worker)
builder.add_node("aggregate", aggregate)
builder.add_conditional_edges(START, dispatch, ["worker"])
builder.add_edge("worker", "aggregate")
builder.add_edge("aggregate", END)
graph = builder.compile()

graph.invoke({"topics": ["AI", "Bio", "Energy"], "findings": []})