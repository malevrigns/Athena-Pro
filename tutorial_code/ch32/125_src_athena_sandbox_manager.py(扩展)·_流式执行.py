"""流式执行:输出实时回流到调用方"""
import asyncio
from typing import AsyncIterator


class SandboxManager:
    # ... 之前的代码 ...
    
    async def execute_streaming(
        self,
        cmd: list[str],
        config: SandboxConfig | None = None,
    ) -> AsyncIterator[dict]:
        """
        流式执行版本。
        yield 的字典格式:
          {"type": "stdout"|"stderr", "data": "..."}     # 每个 chunk
          {"type": "done", "exit_code": 0, "duration": 12.3}  # 结束
          {"type": "error", "reason": "timeout"}         # 异常
        """
        config = config or SandboxConfig()
        
        # 在 thread pool 跑 docker 阻塞操作,通过 asyncio Queue 接力
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        def producer():
            """阻塞线程:把 docker 输出推到 queue。"""
            container = None
            t0 = time.perf_counter()
            try:
                container = self.client.containers.create(
                    image=config.image,
                    command=cmd,
                    # ... 上一章的所有安全配置 ...
                    detach=True,
                    stdout=True, stderr=True,
                )
                container.start()
                
                # 流式拿 stdout
                stdout_stream = container.logs(
                    stdout=True, stderr=False, stream=True, follow=True,
                )
                stderr_stream = container.logs(
                    stdout=False, stderr=True, stream=True, follow=True,
                )
                
                # 用两个迭代器,谁先来推谁(简化版,生产用 select)
                for chunk in stdout_stream:
                    if chunk:
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "stdout", "data": chunk.decode("utf-8", errors="replace")},
                        )
                # stdout 流结束 → 容器结束 → 拉 stderr
                for chunk in stderr_stream:
                    if chunk:
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "stderr", "data": chunk.decode("utf-8", errors="replace")},
                        )
                
                exit_info = container.wait(timeout=config.timeout_sec)
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "done",
                        "exit_code": exit_info.get("StatusCode", -1),
                        "duration": time.perf_counter() - t0,
                    },
                )
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "reason": str(e)},
                )
            finally:
                if container is not None:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass
                loop.call_soon_threadsafe(queue.put_nowait, None)   # 哨兵:结束
        
        # 启 producer 线程
        loop.run_in_executor(None, producer)
        
        # 消费 queue 直到 None
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event