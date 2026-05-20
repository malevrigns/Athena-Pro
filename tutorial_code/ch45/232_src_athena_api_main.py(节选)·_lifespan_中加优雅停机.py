@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 启动逻辑 ...
    yield
    # ===== 关闭流程 =====
    logger.info("shutdown_initiated")
    
    # 1) 标记不再接新任务(健康检查会变 not-ready)
    app.state.accepting_new = False
    
    # 2) 等正在跑的任务完成,最多 25 秒(K8s preStop 给了 60s 总预算)
    deadline = time.time() + 25
    while time.time() < deadline:
        running = await count_running_tasks()
        if running == 0:
            break
        logger.info("shutdown_waiting", running=running)
        await asyncio.sleep(2)
    
    # 3) 还没结束的任务,标记为 "aborted_for_shutdown"
    await mark_remaining_tasks_aborted()
    logger.info("shutdown_complete")