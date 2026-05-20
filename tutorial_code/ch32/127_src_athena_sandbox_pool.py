"""沙箱容器预热池"""
from __future__ import annotations
import asyncio
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass

import docker
from docker.models.containers import Container

from athena.config import settings
from athena.observability import logger


@dataclass
class PooledContainer:
    container: Container
    container_id: str
    created_at: float
    used_count: int = 0


class SandboxPool:
    """
    预热的暂停态容器池。
    
    生命周期:
      1. 启动时创建 pool_size 个容器,启动后 pause(进入暂停态)
      2. acquire() 弹出一个,unpause,返回给调用方
      3. 调用方用 exec_run 跑命令(不会重新启动容器)
      4. release() 把容器 reset(清 /tmp、kill 残留进程)、re-pause、放回池
      5. 容器用 N 次后强制 retire 重建,避免脏数据累积
    """
    
    def __init__(self, pool_size: int = 5, max_uses_per_container: int = 50):
        self.client = docker.from_env()
        self.pool_size = pool_size
        self.max_uses_per_container = max_uses_per_container
        self._pool: deque[PooledContainer] = deque()
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """启动时填池子。"""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            for _ in range(self.pool_size):
                pc = await asyncio.to_thread(self._create_paused_container)
                self._pool.append(pc)
            self._initialized = True
            logger.info("sandbox_pool_initialized", size=self.pool_size)
    
    def _create_paused_container(self) -> PooledContainer:
        """创建并启动一个长寿命容器,然后 pause。"""
        # 入口点改成"睡到天荒地老":容器持续存活,不会自己退出
        container = self.client.containers.create(
            image=settings.sandbox_image,
            # tail -f /dev/null 是 "永远不退出" 的经典写法
            command=["tail", "-f", "/dev/null"],
            # 同上一章的所有安全配置
            cpu_quota=100_000, cpu_period=100_000,
            mem_limit="512m", memswap_limit="512m",
            pids_limit=256,
            network_mode="none",
            read_only=True,
            tmpfs={"/tmp": "size=64m,mode=1777", "/workspace": "size=128m,mode=1777"},
            user="1000:1000",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            labels={"athena.kind": "sandbox-pool"},
            detach=True,
            name=f"athena-pool-{uuid.uuid4().hex[:8]}",
        )
        container.start()
        container.pause()
        return PooledContainer(
            container=container,
            container_id=container.id,
            created_at=time.time(),
        )
    
    @asynccontextmanager
    async def acquire(self):
        """获取一个可执行容器。async with 退出时自动归还。"""
        await self.initialize()
        pc = None
        async with self._lock:
            if self._pool:
                pc = self._pool.popleft()
            else:
                # 池子被掏空,临时再建一个(异常情况)
                logger.warning("sandbox_pool_exhausted")
                pc = await asyncio.to_thread(self._create_paused_container)
        
        try:
            await asyncio.to_thread(pc.container.unpause)
            yield pc
        finally:
            try:
                await self._reset_and_return(pc)
            except Exception as e:
                logger.exception("sandbox_pool_return_failed", err=str(e))
                # 销毁这个容器,重建一个补位
                try:
                    pc.container.remove(force=True)
                except Exception:
                    pass
                new_pc = await asyncio.to_thread(self._create_paused_container)
                async with self._lock:
                    self._pool.append(new_pc)
    
    async def _reset_and_return(self, pc: PooledContainer) -> None:
        """归还容器到池子:清理状态 + 决定 retire 或 keep。"""
        pc.used_count += 1
        
        # 用太多次了,退役重建
        if pc.used_count >= self.max_uses_per_container:
            await asyncio.to_thread(pc.container.remove, force=True)
            new_pc = await asyncio.to_thread(self._create_paused_container)
            async with self._lock:
                self._pool.append(new_pc)
            logger.debug("sandbox_pool_container_retired", reused=pc.used_count)
            return
        
        # 重置 /tmp 和 /workspace(它们是 tmpfs,内容会清,但 ls 一下保险)
        try:
            pc.container.exec_run("rm -rf /tmp/* /workspace/*", user="root", privileged=False)
        except Exception:
            pass  # 即使失败也归还
        
        # 杀掉残留的用户进程(防止上一次任务遗漏的进程)
        try:
            pc.container.exec_run("pkill -9 -u sandbox", user="root")
        except Exception:
            pass
        
        # re-pause
        await asyncio.to_thread(pc.container.pause)
        
        async with self._lock:
            self._pool.append(pc)
    
    async def execute_in_pool(
        self,
        cmd: list[str],
        timeout_sec: float = 30,
    ) -> dict:
        """从池子借容器跑命令。"""
        async with self.acquire() as pc:
            # exec_run 在已有容器里跑命令,不需要重启
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    pc.container.exec_run,
                    cmd, user="sandbox", workdir="/workspace",
                    stdout=True, stderr=True, demux=True,
                ),
                timeout=timeout_sec,
            )
            exit_code = result.exit_code
            stdout, stderr = result.output
            return {
                "stdout": (stdout or b"").decode("utf-8", errors="replace"),
                "stderr": (stderr or b"").decode("utf-8", errors="replace"),
                "exit_code": exit_code,
            }
    
    async def shutdown(self) -> None:
        """优雅停机:销毁所有池中容器。"""
        async with self._lock:
            while self._pool:
                pc = self._pool.popleft()
                try:
                    pc.container.remove(force=True)
                except Exception:
                    pass
            logger.info("sandbox_pool_shutdown")


# 全局单例
_pool: SandboxPool | None = None

def get_sandbox_pool() -> SandboxPool:
    global _pool
    if _pool is None:
        _pool = SandboxPool(pool_size=settings.sandbox_pool_size)
    return _pool