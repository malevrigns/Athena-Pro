"""沙箱化的 Python / Bash 工具"""
from __future__ import annotations
import textwrap

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from athena.sandbox.manager import get_sandbox_manager, SandboxConfig
from athena.observability import logger


# ============ Python REPL ============
class PythonReplArgs(BaseModel):
    code: str = Field(..., description="要执行的 Python 代码。stdout/stderr 会被捕获返回")
    timeout_sec: float = Field(default=30, le=120, description="最长 120 秒")


@tool("python_repl", args_schema=PythonReplArgs)
async def python_repl(code: str, timeout_sec: float = 30) -> str:
    """在隔离 Docker 沙箱里执行 Python 代码。
    
    适合:数据分析、数学计算、画图(图会保存到 /workspace/out.png 自动返回链接)、
    跑一段算法验证逻辑。
    
    不适合:网络请求(沙箱默认无网)、长时间运行任务、文件系统持久化操作。
    
    重要:
    - 每次调用启一个新沙箱,没有上下文延续(变量不跨调用)。如果要"延续",请把全部代码一次性传入
    - 沙箱内已预装 numpy/pandas/scipy/sklearn/matplotlib/seaborn
    - 输出超过 64KB 会被截断
    """
    # 在代码前后加些壳:让输出更友好
    wrapped = textwrap.dedent(f"""
        import sys, traceback
        try:
{textwrap.indent(code, '            ')}
        except Exception:
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
    """)
    
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        cmd=["python", "-c", wrapped],
        config=SandboxConfig(timeout_sec=timeout_sec, network_mode="none"),
    )
    
    if result.timed_out:
        return f"⏱ 执行超时(> {timeout_sec}s),已被强制终止。\n" \
               f"部分输出:\n{result.stdout[:1000]}"
    if result.out_of_memory:
        return f"💥 内存超限(> 512MB),容器被 OOM killer 终止。"
    
    parts = []
    if result.stdout:
        parts.append(f"--- stdout ---\n{result.stdout}")
    if result.stderr:
        parts.append(f"--- stderr ---\n{result.stderr}")
    if result.exit_code != 0:
        parts.append(f"--- exit code ---\n{result.exit_code}")
    return "\n".join(parts) or "(无输出)"


# ============ Bash 工具 ============
class BashArgs(BaseModel):
    command: str = Field(..., description="要执行的 shell 命令(单行或带管道)")
    timeout_sec: float = Field(default=30, le=60)


@tool("bash", args_schema=BashArgs)
async def bash_tool(command: str, timeout_sec: float = 30) -> str:
    """在隔离 Docker 沙箱里执行 shell 命令。
    
    适合:ls / grep / sed / awk 等文本处理,git 等代码操作(只读模式),数据预处理。
    
    重要:
    - 命令在沙箱里跑,文件系统是临时的(容器销毁就丢)
    - 没有网络,无法 curl / wget / git clone(远程仓库)
    - 不能 sudo,不能改系统文件
    - 受 PermissionEngine 管控,危险命令会被拒绝或要求审批
    """
    mgr = get_sandbox_manager()
    result = await mgr.execute(
        cmd=["bash", "-c", command],
        config=SandboxConfig(timeout_sec=timeout_sec, network_mode="none"),
    )
    
    if result.timed_out:
        return f"⏱ 命令超时(> {timeout_sec}s)"
    
    output = result.stdout
    if result.stderr:
        output += f"\n[stderr]\n{result.stderr}"
    if result.exit_code != 0:
        output += f"\n[exit {result.exit_code}]"
    return output or "(无输出)"