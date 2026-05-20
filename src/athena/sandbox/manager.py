from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from athena.tools.sandbox_tools import CommandResult, LocalSandbox


@dataclass
class SandboxConfig:
    timeout_sec: float = 20.0
    network_mode: str = "none"
    memory_limit_mb: int = 512
    read_only: bool = True


class SandboxManager:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(".athena-data/sandbox")
        self.root.mkdir(parents=True, exist_ok=True)
        self.local = LocalSandbox(self.root)

    async def execute(self, cmd: list[str], config: SandboxConfig | None = None) -> CommandResult:
        config = config or SandboxConfig()
        return await self.local.run(" ".join(cmd), timeout_sec=config.timeout_sec)
