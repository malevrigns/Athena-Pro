"""Athena FastAPI 服务入口"""
from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from athena.api.schemas import (
    CreateTaskRequest, CreateTaskResponse, TaskStatusResponse, ApproveRequest,
)
from athena.api.streaming import sse_event_stream
from athena.graph.builders import build_main_graph
from athena.observability import logger, configure_observability
from athena.recovery import recover_pending_tasks
from athena.store.checkpointer import lifespan_pg


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动 / 停机生命周期。"""
    configure_observability()                        # 初始化 LangSmith / OTel
    async with lifespan_pg():                        # 起 Postgres 池
        # 启动时恢复未完成任务(只在 leader 上跑,这里简化)
        await recover_pending_tasks(max_recover=20)
        app.state.graph = await build_main_graph()
        logger.info("api_ready")
        yield
        logger.info("api_shutdown")


app = FastAPI(
    title="Athena · Research Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/research", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest) -> CreateTaskResponse:
    """创建研究任务。立刻返回 task_id,真正执行通过 SSE 流。"""
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    
    initial_state = {
        "question": req.question,
        "user_id": req.user_id,
        "research_plan": [],
        "findings": [],
        "revision_count": 0,
    }
    
    # 把初始 state 写入 checkpointer(创建任务记录)
    config = {"configurable": {"thread_id": task_id}}
    await app.state.graph.aupdate_state(config, initial_state)
    
    logger.info("task_created", task_id=task_id, question=req.question[:80])
    return CreateTaskResponse(task_id=task_id, stream_url=f"/v1/research/{task_id}/stream")


@app.get("/v1/research/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE 流:把图的每一步事件推到客户端。"""
    config = {"configurable": {"thread_id": task_id}}
    
    # 检查任务是否存在
    snapshot = await app.state.graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(404, f"task {task_id} not found")
    
    return StreamingResponse(
        sse_event_stream(app.state.graph, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",               # nginx 不要缓冲
        },
    )


@app.post("/v1/research/{task_id}/approve")
async def approve_plan(task_id: str, req: ApproveRequest):
    """HITL:批准或修改研究计划。"""
    from langgraph.types import Command
    config = {"configurable": {"thread_id": task_id}}
    
    # 把人工决策作为 resume 值传回去
    resume_payload = {
        "action": req.action,                        # "approve" | "modify" | "reject"
        "modified_plan": req.modified_plan,
    }
    
    # 注意:不阻塞,立刻返回。客户端继续在 SSE 流上接收后续事件
    await app.state.graph.aupdate_state(
        config,
        None,
        as_node="__interrupt__",                     # 这种写法在 1.1+ 比 ainvoke(Command) 灵活
    )
    
    return {"status": "resumed", "action": req.action}


@app.get("/v1/research/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """查询任务当前状态(轮询用)。"""
    config = {"configurable": {"thread_id": task_id}}
    snapshot = await app.state.graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(404)
    
    state = snapshot.values
    return TaskStatusResponse(
        task_id=task_id,
        status="finished" if not snapshot.next else "running",
        current_node=snapshot.next[0] if snapshot.next else None,
        findings_count=len(state.get("findings", [])),
        final_report=state.get("final_report"),
    )