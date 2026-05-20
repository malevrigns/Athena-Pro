"""Athena CLI 主应用"""
from __future__ import annotations
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from athena_cli.screens.home import HomeScreen
from athena_cli.screens.history import HistoryScreen
from athena_cli.api import AthenaClient


class AthenaApp(App):
    """Athena CLI 客户端"""
    
    TITLE = "Athena"
    SUB_TITLE = "AI Research Workstation"
    CSS_PATH = Path(__file__).parent / "theme.tcss"
    
    BINDINGS = [
        Binding("ctrl+n", "new_task", "新研究"),
        Binding("ctrl+h", "show_history", "历史"),
        Binding("ctrl+c", "quit_safely", "退出"),
        Binding("escape", "abort_task", "停止"),
    ]
    
    SCREENS = {
        "home": HomeScreen,
        "history": HistoryScreen,
    }
    
    def __init__(self, *, server_url: str, token: str):
        super().__init__()
        self.client = AthenaClient(server_url=server_url, token=token)
        self.current_task_id: str | None = None
    
    async def on_mount(self) -> None:
        await self.push_screen("home")
    
    # ===== Actions =====
    async def action_new_task(self) -> None:
        await self.switch_screen("home")
    
    async def action_show_history(self) -> None:
        await self.push_screen("history")
    
    async def action_abort_task(self) -> None:
        if self.current_task_id:
            await self.client.interrupt_task(self.current_task_id)
            self.notify(f"已请求停止任务 {self.current_task_id[:8]}")
    
    async def action_quit_safely(self) -> None:
        # 给后端发"客户端断开"信号,让运行中的任务保持(可 /resume 续上)
        await self.client.close()
        self.exit()