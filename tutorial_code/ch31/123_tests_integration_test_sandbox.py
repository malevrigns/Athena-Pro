"""沙箱集成测试 - 验证隔离效果"""
import pytest
from athena.sandbox.manager import get_sandbox_manager, SandboxConfig


@pytest.mark.asyncio
async def test_normal_python_execution():
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        ["python", "-c", "print('hello'); import sys; print(sys.version)"],
    )
    assert result.success
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_network_blocked():
    """默认 no-network,要确保 LLM 真的连不出去。"""
    mgr = get_sandbox_manager()
    result = await mgr.execute([
        "python", "-c",
        "import socket; socket.create_connection(('1.1.1.1', 443), timeout=2)"
    ])
    assert not result.success                              # 应该失败
    assert "network" in result.stderr.lower() or "unreachable" in result.stderr.lower() \
        or "name or service" in result.stderr.lower()


@pytest.mark.asyncio
async def test_filesystem_readonly():
    """rootfs 应该只读。"""
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        ["bash", "-c", "echo 'evil' > /etc/passwd"],
    )
    assert not result.success
    assert "read-only" in result.stderr.lower()


@pytest.mark.asyncio
async def test_timeout_kills_runaway():
    """死循环要被超时杀死。"""
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        ["python", "-c", "while True: pass"],
        config=SandboxConfig(timeout_sec=2.0),
    )
    assert result.timed_out
    assert result.duration_sec < 5    # 超时 + 清理时间


@pytest.mark.asyncio
async def test_fork_bomb_limited():
    """pids_limit 应该挡住 fork bomb。"""
    mgr = get_sandbox_manager()
    # 这是个被简化的 fork bomb(不无限,以防真把 host 搞炸)
    result = await mgr.execute(
        ["bash", "-c", "for i in $(seq 1 1000); do sleep 1 & done; wait"],
        config=SandboxConfig(timeout_sec=3.0, pids_limit=50),
    )
    # 应该报错或被超时杀
    assert "Resource temporarily unavailable" in result.stderr \
        or result.timed_out


@pytest.mark.asyncio
async def test_oom_killer():
    """超内存应该被 OOM killer。"""
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        ["python", "-c", "x = ' ' * (10 ** 9)"],     # 1GB 字符串
        config=SandboxConfig(mem_limit="128m"),
    )
    assert result.out_of_memory or not result.success