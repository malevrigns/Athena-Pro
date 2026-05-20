from langgraph.types import Send

# 在 supervisor_node 里:
def supervisor_node(state):
    pending_topics = _find_pending(state)
    
    if pending_topics:
        # ↓↓↓ 关键:返回 list[Send],每个 Send 是一个并行分支
        return Command(
            goto=[
                Send("researcher", {
                    "topic_id": t["id"],
                    "topic": t["topic"],
                    "why": t["why"],
                    "task_id": state["task_id"],
                })
                for t in pending_topics
            ],
            update={"phase": Phase.RESEARCHING, ...},
        )