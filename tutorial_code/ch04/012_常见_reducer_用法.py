import operator
from typing import Annotated, TypedDict

class State(TypedDict):
    # 字符串列表追加(用 operator.add 就是 + 操作)
    findings: Annotated[list[str], operator.add]
    
    # 数字累加
    total_cost: Annotated[float, operator.add]
    
    # 自定义 reducer
    visited_nodes: Annotated[set[str], lambda old, new: old | new]
    
    # 没有 reducer,默认覆盖(适合"当前状态"类字段)
    current_step: str