def my_router(state) -> str:
    return "writer" if state["score"] > 0.8 else "researcher"

builder.add_conditional_edges("evaluator", my_router)
# 等价于上面那种写法