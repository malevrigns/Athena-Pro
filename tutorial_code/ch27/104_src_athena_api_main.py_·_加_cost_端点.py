@app.get("/v1/research/{task_id}/cost")
async def get_task_cost(task_id: str) -> dict:
    """查询任务累计成本。"""
    config = {"configurable": {"thread_id": task_id}}
    snapshot = await app.state.graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(404)
    
    ledger_dict = snapshot.values.get("cost_ledger", {})
    return {
        "task_id": task_id,
        "spent_usd": ledger_dict.get("spent_usd", 0),
        "budget_usd": ledger_dict.get("budget_usd", 0),
        "remaining_usd": ledger_dict.get("budget_usd", 0) - ledger_dict.get("spent_usd", 0),
        "by_model": ledger_dict.get("by_model", {}),
        "by_node": ledger_dict.get("by_node", {}),
        "n_llm_calls": ledger_dict.get("n_calls", 0),
    }