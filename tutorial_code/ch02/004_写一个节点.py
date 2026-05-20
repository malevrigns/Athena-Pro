def answer_node(state: State) -> dict:
    # 读 state
    question = state["question"]
    # 干活
    answer = f"关于「{question}」,我的回答是 ..."
    # 返回要修改的字段(不需要返回整个 state)
    return {
        "answer": answer,
        "step_count": state.get("step_count", 0) + 1,
    }