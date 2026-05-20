"""
关键操作前,让人类审核。
"""
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt


class State(TypedDict):
    messages: Annotated[list, add_messages]
    proposed_action: dict
    approved: bool


def propose(state):
    return {"proposed_action": {"type": "delete", "target": "db.users"}}


def human_approval(state) -> Command[Literal["execute", "__end__"]]:
    decision = interrupt({
        "action": state["proposed_action"],
        "question": "是否批准?"
    })
    if decision == "yes":
        return Command(goto="execute", update={"approved": True})
    return Command(goto=END, update={"approved": False})


def execute(state):
    # 真正的副作用放这里
    print(f"执行: {state['proposed_action']}")
    return {}


builder = StateGraph(State)
builder.add_node("propose", propose)
builder.add_node("approval", human_approval)
builder.add_node("execute", execute)
builder.add_edge(START, "propose")
builder.add_edge("propose", "approval")
builder.add_edge("execute", END)

graph = builder.compile(checkpointer=InMemorySaver())

# 用法
config = {"configurable": {"thread_id": "tx-1"}}
graph.invoke({"messages": []}, config=config)
# 检查 state.next 是否是 ("approval",)
graph.invoke(Command(resume="yes"), config=config)