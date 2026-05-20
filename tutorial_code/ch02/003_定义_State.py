from typing import TypedDict

class State(TypedDict):
    question: str       # 用户问题
    answer: str         # 答案
    step_count: int     # 走了几步