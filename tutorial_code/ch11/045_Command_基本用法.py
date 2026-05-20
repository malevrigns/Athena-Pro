from typing import Literal
from langgraph.types import Command

def my_node(state) -> Command[Literal["writer", "reviewer"]]:
    # 干一些活
    new_message = call_llm(state)
    
    return Command(
        update={"messages": [new_message]},   # 状态更新
        goto="writer",                        # 下一步去哪
    )