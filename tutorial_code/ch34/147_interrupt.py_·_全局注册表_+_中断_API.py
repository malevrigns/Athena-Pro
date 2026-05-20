# 全局注册表:task_id → abort event
_task_aborts: dict[str, asyncio.Event] = {}
_lock = asyncio.Lock()


async def register_task(task_id: str) -> asyncio.Event:
    async with _lock:
        event = asyncio.Event()
        _task_aborts[task_id] = event
        return event


async def interrupt_running_graph(graph, task_id: str) -> bool:
    """触发某任务的中断。返回是否成功通知。"""
    async with _lock:
        event = _task_aborts.get(task_id)
    if not event:
        return False
    event.set()
    
    # 把中断意图也写进 graph state,supervisor 节点会读它
    config = {"configurable": {"thread_id": task_id}}
    await graph.aupdate_state(config, {"abort_requested": True})
    return True


async def unregister_task(task_id: str) -> None:
    async with _lock:
        _task_aborts.pop(task_id, None)