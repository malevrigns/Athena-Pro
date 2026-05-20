"""ReportView · 用 Rich 渲染 Markdown 报告 + 引用脚注"""
from __future__ import annotations
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Markdown, ListView, ListItem, Label


class ReportScreen(Screen):
    """报告 + 来源面板"""
    
    BINDINGS = [
        ("o", "open_browser", "在浏览器打开报告"),
        ("c", "copy_clipboard", "复制 Markdown"),
        ("q", "back", "返回"),
    ]
    
    def __init__(self, markdown: str, metadata: dict | None):
        super().__init__()
        self.markdown = markdown
        self.metadata = metadata or {}
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # 主体
            with Vertical(id="report-body"):
                yield Markdown(self.markdown)
            # 引用面板
            with Vertical(id="report-citations"):
                yield Label("[bold]参考来源[/]")
                yield self._build_citation_list()
        yield Footer()
    
    def _build_citation_list(self) -> ListView:
        items = []
        for c in self.metadata.get("citations", []):
            items.append(ListItem(
                Label(f"[{c['number']}] {c['title'][:40]}..."),
                Label(f"  [dim]{c['url'][:50]}[/]"),
            ))
        return ListView(*items)
    
    async def action_open_browser(self) -> None:
        import webbrowser
        # 后端有 web URL,打开它
        url = f"{self.app.client.web_url}/task/{self.app.current_task_id}"
        webbrowser.open(url)
    
    async def action_copy_clipboard(self) -> None:
        import pyperclip
        pyperclip.copy(self.markdown)
        self.notify("已复制 Markdown")
    
    async def action_back(self) -> None:
        await self.app.pop_screen()