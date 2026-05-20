from typing import Literal
from langgraph.types import Command

def evaluator(state) -> Command[Literal["writer", "researcher"]]:
    score = compute_score(state)
    next_node = "writer" if score > 0.8 else "researcher"
    return Command(
        update={"score": score},
        goto=next_node,
    )

builder.add_node("evaluator", evaluator)
# 完全不需要 add_conditional_edges!