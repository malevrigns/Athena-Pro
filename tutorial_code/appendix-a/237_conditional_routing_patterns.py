# 方式 1:add_conditional_edges
def router(state) -> str:
    return "b" if state["score"] > 0.5 else "c"

builder.add_conditional_edges("a", router)

# 方式 2:Command (推荐用于多 Agent)
from typing import Literal
from langgraph.types import Command

def node_a(state) -> Command[Literal["b", "c"]]:
    next_node = "b" if state["score"] > 0.5 else "c"
    return Command(goto=next_node, update={"score": state["score"]})

# 方式 3:Send(并行扇出)
from langgraph.types import Send

def fanout(state):
    return [Send("worker", {"task": t}) for t in state["tasks"]]

builder.add_conditional_edges("dispatcher", fanout, ["worker"])