@app.post("/v1/research", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest, background: BackgroundTasks):
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": task_id}}
    
    # 起一个后台任务,跑图直到 END 或 interrupt
    background.add_task(
        run_graph_to_interrupt_or_end,
        app.state.graph,
        config,
        initial_state={
            "question": req.question,
            "task_id": task_id,
            "user_id": req.user_id,
            "research_plan": [],
            "findings": [],
            "revision_count": 0,
        },
    )
    
    # 同时起超时哨兵
    background.add_task(
        schedule_interrupt_timeout,
        graph=app.state.graph,
        task_id=task_id,
        deadline_sec=settings.plan_review_timeout_sec,
        default_resume={"action": "approve"},        # 超时默认批准
    )
    
    return CreateTaskResponse(task_id=task_id, stream_url=f"/v1/research/{task_id}/stream")