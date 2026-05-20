async def _replay_stream(graph, config):
    # 1. 重放历史
    history = []
    async for snap in graph.aget_state_history(config):
        history.append(snap)
    history.reverse()                              # aget_state_history 是 newest first
    
    yield _format_sse("replay_start", {"total": len(history)})
    
    for i, snap in enumerate(history):
        # 每个 snapshot 对应一次节点更新
        meta = snap.metadata or {}
        writes = meta.get("writes", {})
        for node_name, update in writes.items():
            if node_name in ("__start__", "__end__"):
                continue
            yield _format_sse("replay_event", {
                "index": i,
                "node": node_name,
                "summary": _summarize_update(update) if update else {},
                "ts": snap.created_at.isoformat() if snap.created_at else None,
            })
    
    yield _format_sse("replay_end", {})
    
    # 2. 如果还没完,接实时流
    if snapshot := await graph.aget_state(config):
        if snapshot.next:
            yield _format_sse("live_start", {})
            async for chunk in graph.astream(None, config=config,
                                             stream_mode=["updates"]):
                mode, payload = chunk
                if mode == "updates":
                    for node, update in payload.items():
                        yield _format_sse("node_update", {
                            "node": node,
                            "summary": _summarize_update(update),
                        })