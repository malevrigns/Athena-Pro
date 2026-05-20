from athena.llm_factory import get_llm

@trace_node("planner")
@budget_guard("planner")
async def planner_node(state):
    llm = get_llm(model="gpt-4o-mini", node_name="planner")
    # ... 用 llm ...