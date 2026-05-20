def evaluator(state):
    score = compute_score(state)
    return {"score": score}

def router(state):
    return "writer" if state["score"] > 0.8 else "researcher"

builder.add_node("evaluator", evaluator)
builder.add_conditional_edges("evaluator", router)