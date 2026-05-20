"""流式输出区:类似 ChatGPT 的打字机效果"""
from __future__ import annotations
from textual.widgets import RichLog
from rich.text import Text


class StreamPane(RichLog):
    """显示 LLM 流式输出 + 节点摘要 + 系统消息"""
    
    DEFAULT_CSS = """
    StreamPane { background: $surface; padding: 1 2; }
    """
    
    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, **kwargs)
        self._buffer = ""
        self._current_line: Text | None = None
    
    def append_token(self, token: str) -> None:
        """LLM 输出一个 token。"""
        self._buffer += token
        # 如果累计到换行,提交一行
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.write(line)
    
    def append_node_summary(self, node: str, summary: str) -> None:
        """节点完成时插入一行总结。"""
        # flush 当前 buffer
        if self._buffer:
            self.write(self._buffer)
            self._buffer = ""
        self.write(f"\n[dim]── {node} ──[/]")
        self.write(f"  {summary}\n")
    
    def append_system_msg(self, msg: str) -> None:
        self.write(msg)
    
    def append_error(self, err: str) -> None:
        self.write(f"[red bold]❌ {err}[/]")
    
    def mark_done(self) -> None:
        # flush 残余
        if self._buffer:
            self.write(self._buffer)
            self._buffer = ""
        self.write("\n[green bold]✓ 任务完成[/]\n")