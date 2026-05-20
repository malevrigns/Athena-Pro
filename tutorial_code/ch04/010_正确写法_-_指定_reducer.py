from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages   # ← 关键!

class State(TypedDict):
    # ↓↓↓ 告诉 LangGraph:用 add_messages 来合并这个字段
    messages: Annotated[list[AnyMessage], add_messages]