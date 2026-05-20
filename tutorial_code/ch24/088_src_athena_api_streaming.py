"""SSE 流式事件发送"""
from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator

from athena.observability import logger


def _format_sse(event_type: str, data: dict) -> str:
    """格式化为 SSE 协议字符串。"""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def sse_event_stream(graph, config: dict) -> AsyncGenerator[str, None]:
    """订阅图的执行,把每个事件转成 SSE。"""
    task_id = config["configurable"]["thread_id"]
    
    try:
        # 立刻发一条 "connected" 让前端知道流通了
        yield _format_sse("connected", {"task_id": task_id})
        
        async for chunk in graph.astream(
            None,                                     # None = 从最新 checkpoint 继续
            config=config,
            stream_mode=["updates", "messages", "custom"],
        ):
            mode, payload = chunk
            
            if mode == "updates":
                # 每个节点完成的事件
                for node_name, node_update in payload.items():
                    yield _format_sse("node_update", {
                        "node": node_name,
                        "summary": _summarize_update(node_update),
                    })
            
            elif mode == "messages":
                # LLM token 流(打字机效果)
                msg_chunk, meta = payload
                if msg_chunk.content:
                    yield _format_sse("token", {
                        "node": meta.get("langgraph_node", "?"),
                        "content": msg_chunk.content,
                    })
            
            elif mode == "custom":
                # 节点内部用 get_stream_writer() 发出的事件
                yield _format_sse("custom", payload)
            
            # 心跳,防 nginx / proxy 超时
            await asyncio.sleep(0)                   # 让出控制权
        
        # 流结束
        snapshot = await graph.aget_state(config)
        yield _format_sse("done", {
            "task_id": task_id,
            "final_report": snapshot.values.get("final_report"),
            "metadata": snapshot.values.get("report_metadata"),
        })
    
    except asyncio.CancelledError:
        # 客户端断开连接,不算错误
        logger.info("sse_cancelled", task_id=task_id)
        raise
    except Exception as e:
        logger.exception("sse_error", task_id=task_id, error=str(e))
        yield _format_sse("error", {"error": str(e), "type": type(e).__name__})


def _summarize_update(node_update: dict) -> dict:
    """把节点更新精简成前端友好的摘要(不要把整个 state 推过去)。"""
    if not node_update:
        return {}
    if "messages" in node_update:
        msgs = node_update["messages"]
        if msgs:
            last = msgs[-1]
            return {
                "type": "message",
                "name": getattr(last, "name", None),
                "preview": (last.content or "")[:200],
            }
    if "findings" in node_update:
        return {"type": "finding_added", "count": len(node_update["findings"])}
    return {"type": "state_change", "keys": list(node_update.keys())}