"""沙箱容器生命周期管理"""
from __future__ import annotations
import asyncio
import io
import os
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import docker
from docker.errors import ContainerError, NotFound
from docker.models.containers import Container

from athena.config import settings
from athena.observability import logger
from athena.observability.metrics import (
    SANDBOX_EXECUTIONS, SANDBOX_DURATION, SANDBOX_TIMEOUTS,
)


@dataclass
class SandboxConfig:
    """每次执行的沙箱配置。"""
    image: str = "athena/sandbox:latest"
    timeout_sec: float = 60.0
    cpu_limit: float = 1.0                            # 1 core
    mem_limit: str = "512m"                           # 512 MB
    pids_limit: int = 256
    network_mode: Literal["none", "bridge"] = "none"  # 默认无网
    
    # 挂载只读资源(用户提供的数据文件)
    read_only_mounts: dict[str, str] = field(default_factory=dict)  # host_path: container_path
    
    # 环境变量(白名单,谨慎)
    env: dict[str, str] = field(default_factory=dict)
    
    # 标识
    session_id: str = ""
    task_id: str = ""


@dataclass
class SandboxResult:
    """沙箱执行结果。"""
    stdout: str
    stderr: str
    exit_code: int
    duration_sec: float
    timed_out: bool = False
    out_of_memory: bool = False
    
    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.out_of_memory


class SandboxManager:
    """
    管理沙箱容器的创建 / 执行 / 清理。
    设计:每次执行用一次性容器(create → exec → remove)。
    性能优化(下文):预热池 + 暂停态容器复用。
    """
    
    def __init__(self):
        # docker.from_env() 会从环境读取连接信息
        self.client = docker.from_env()
        self._verify_image_exists()
    
    def _verify_image_exists(self) -> None:
        try:
            self.client.images.get(settings.sandbox_image)
        except docker.errors.ImageNotFound:
            logger.warning("sandbox_image_missing", image=settings.sandbox_image)
            raise RuntimeError(
                f"沙箱镜像 {settings.sandbox_image} 不存在,先运行:"
                f"docker build -t athena/sandbox:latest docker/sandbox/"
            )
    
    async def execute(
        self,
        cmd: list[str],
        stdin_data: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SandboxResult:
        """
        在沙箱里跑一条命令,返回结果。
        cmd 是命令列表,如 ["python", "-c", "print(1)"] 或 ["bash", "-c", "ls"]。
        """
        config = config or SandboxConfig()
        return await asyncio.to_thread(
            self._execute_sync, cmd, stdin_data, config,
        )
    
    def _execute_sync(
        self,
        cmd: list[str],
        stdin_data: str | None,
        config: SandboxConfig,
    ) -> SandboxResult:
        """同步执行(放到 thread pool 跑)。"""
        container_name = f"athena-sb-{uuid.uuid4().hex[:8]}"
        t0 = time.perf_counter()
        timed_out = False
        out_of_memory = False
        container: Container | None = None
        
        try:
            # ========== 创建容器 ==========
            volumes = {
                host: {"bind": container, "mode": "ro"}
                for host, container in config.read_only_mounts.items()
            }
            
            container = self.client.containers.create(
                image=config.image,
                command=cmd,
                name=container_name,
                # 资源限制
                cpu_quota=int(config.cpu_limit * 100_000),
                cpu_period=100_000,
                mem_limit=config.mem_limit,
                memswap_limit=config.mem_limit,           # 禁止 swap 扩展内存
                pids_limit=config.pids_limit,
                # 安全
                network_mode=config.network_mode,
                read_only=True,                            # 根文件系统只读
                tmpfs={                                    # /tmp 挂个内存盘
                    "/tmp": "size=64m,mode=1777",
                    "/workspace": "size=128m,mode=1777",   # workspace 也走 tmpfs
                },
                user="1000:1000",
                cap_drop=["ALL"],                          # 删除所有 Linux capabilities
                security_opt=["no-new-privileges"],        # 禁止特权提升
                # 标签(方便后续运维 / 监控)
                labels={
                    "athena.session_id": config.session_id,
                    "athena.task_id": config.task_id,
                    "athena.kind": "sandbox",
                },
                # 容器停止时自动清理
                auto_remove=False,                          # 我们手动清,要拿 logs
                detach=True,
                stdin_open=stdin_data is not None,
                # 挂载
                volumes=volumes,
                environment=config.env,
            )
            
            # ========== 启动 + 喂 stdin ==========
            container.start()
            
            if stdin_data is not None:
                sock = container.attach_socket(params={"stdin": 1, "stream": 1})
                try:
                    sock._sock.sendall(stdin_data.encode())
                    sock._sock.shutdown(1)                # 关写端,sandbox 才知道 EOF
                finally:
                    sock.close()
            
            # ========== 等结束(带超时)==========
            try:
                exit_info = container.wait(timeout=config.timeout_sec)
                exit_code = exit_info.get("StatusCode", -1)
            except Exception:
                # 超时
                timed_out = True
                exit_code = -1
                SANDBOX_TIMEOUTS.inc()
                try:
                    container.kill(signal="SIGKILL")
                except Exception:
                    pass
            
            # ========== 收集输出 ==========
            try:
                stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            except Exception:
                stdout = stderr = ""
            
            # 截断超长输出(防止打爆主进程内存)
            MAX_OUT = 64 * 1024
            if len(stdout) > MAX_OUT:
                stdout = stdout[:MAX_OUT] + f"\n... [truncated, total {len(stdout)} bytes]"
            if len(stderr) > MAX_OUT:
                stderr = stderr[:MAX_OUT] + f"\n... [truncated]"
            
            # ========== 判断是否 OOM ==========
            try:
                state = container.attrs.get("State", {})
                out_of_memory = state.get("OOMKilled", False)
            except Exception:
                pass
            
            duration = time.perf_counter() - t0
            SANDBOX_DURATION.observe(duration)
            SANDBOX_EXECUTIONS.labels(
                status="timeout" if timed_out else ("oom" if out_of_memory else ("ok" if exit_code == 0 else "error"))
            ).inc()
            
            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_sec=duration,
                timed_out=timed_out,
                out_of_memory=out_of_memory,
            )
        
        finally:
            # 不论成功失败都清理容器
            if container is not None:
                try:
                    container.remove(force=True)
                except NotFound:
                    pass
                except Exception as e:
                    logger.warning("sandbox_cleanup_failed", err=str(e))


# 全局单例
_manager: SandboxManager | None = None

def get_sandbox_manager() -> SandboxManager:
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager