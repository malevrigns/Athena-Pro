def my_router(state) -> str:
    """根据 state 决定下一步去哪个节点。返回值必须是节点名(或 END)。"""
    if state["score"] > 0.8:
        return "approved"
    else:
        return "rejected"

builder.add_conditional_edges(
    "evaluator",        # 从哪个节点出发
    my_router,          # 路由函数
    {                   # 路由函数返回值 → 实际节点名(可选,默认按返回值取)
        "approved": "writer",
        "rejected": "researcher",
    }
)