from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class LocalSandbox:
    """Small local sandbox used for demos.

    The production tutorial chapter explains Docker isolation. This local version is intentionally
    restrictive and suitable for tests: it runs in a temp working directory, has a timeout, and
    rejects obvious destructive shell forms.
    """

    denied_tokens = {"rm -rf", "mkfs", ":(){", "shutdown", "reboot", "sudo"}

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path(".athena-data/sandbox")
        self.workdir.mkdir(parents=True, exist_ok=True)

    def validate(self, command: str) -> None:
        lowered = command.lower()
        for token in self.denied_tokens:
            if token in lowered:
                raise PermissionError(f"Command denied by local sandbox policy: {token}")

    async def run(self, command: str, timeout_sec: float = 20.0) -> CommandResult:
        self.validate(command)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            return CommandResult(out.decode(), err.decode(), proc.returncode or 0)
        except asyncio.TimeoutError:
            proc.kill()
            return CommandResult("", f"Timed out after {timeout_sec}s", -1, timed_out=True)


async def python_repl(code: str, timeout_sec: float = 20.0) -> str:
    sandbox = LocalSandbox()
    command = "python - <<'PY'\n" + code + "\nPY"
    result = await sandbox.run(command, timeout_sec=timeout_sec)
    return result.stdout + ("\n" + result.stderr if result.stderr else "")


async def bash_tool(command: str, timeout_sec: float = 20.0) -> str:
    sandbox = LocalSandbox()
    safe = shlex.split(command)
    if not safe:
        return ""
    result = await sandbox.run(command, timeout_sec=timeout_sec)
    return result.stdout + ("\n" + result.stderr if result.stderr else "")
