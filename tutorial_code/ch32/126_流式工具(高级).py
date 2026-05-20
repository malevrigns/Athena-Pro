from langgraph.config import get_stream_writer

@tool("python_repl_streaming")
async def python_repl_streaming(code: str) -> str:
    writer = get_stream_writer()                    # 拿到当前节点的 stream writer
    
    mgr = get_sandbox_manager()
    full_output = []
    async for event in mgr.execute_streaming(cmd=["python", "-c", code]):
        if event["type"] in ("stdout", "stderr"):
            full_output.append(event["data"])
            # 把这块输出推到 SSE 流,前端能看到实时回显
            writer({"sandbox_chunk": event["data"], "stream": event["type"]})
        elif event["type"] == "done":
            writer({"sandbox_done": True, "exit_code": event["exit_code"]})
    
    return "".join(full_output)