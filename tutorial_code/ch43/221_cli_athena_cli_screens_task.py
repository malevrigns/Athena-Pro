"""任务运行屏 · 流式渲染 + 节点流程 + Cost"""
from __future__ import annotations
import asyncio
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from athena_cli.widgets.flow_graph import FlowGraphWidget
from athena_cli.widgets.stream_pane import StreamPane
from athena_cli.widgets.cost_bar import CostBar
from athena_cli.widgets.report_view import ReportView


class TaskScreen(Screen):
    """任务运行 / 报告显示"""
    
    BINDINGS = [
        ("escape", "abort", "停止"),
        ("ctrl+r", "view_report", "查看报告"),
        ("ctrl+s", "save_report", "导出"),
    ]
    
    def __init__(self, task_id: str):
        super().__init__()
        self.task_id = task_id
        self._stream_task: asyncio.Task | None = None
        self._aborted = False
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="task-main"):
            # 左:流程图
            with Vertical(id="task-left"):
                yield Static("[bold]执行流程[/]", classes="section-title")
                yield FlowGraphWidget(id="flow-graph")
            # 右:流式输出 / 报告
            with Vertical(id="task-right"):
                yield StreamPane(id="stream-pane")
        yield CostBar(self.task_id, id="cost-bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        # 启动 SSE 流处理
        self._stream_task = asyncio.create_task(self._consume_stream())
    
    async def _consume_stream(self) -> None:
        flow = self.query_one("#flow-graph", FlowGraphWidget)
        stream = self.query_one("#stream-pane", StreamPane)
        cost_bar = self.query_one("#cost-bar", CostBar)
        
        try:
            async for event in self.app.client.stream_task(self.task_id):
                if self._aborted:
                    return
                
                etype = event.get("type")
                if etype == "node_update":
                    flow.set_node_status(event["node"], "done")
                    summary = event.get("summary", {}).get("preview", "")
                    if summary:
                        stream.append_node_summary(event["node"], summary)
                
                elif etype == "token":
                    node = event.get("node")
                    if node:
                        flow.set_node_status(node, "running")
                    stream.append_token(event["content"])
                
                elif etype == "done":
                    stream.mark_done()
                    final_report = event.get("final_report")
                    if final_report:
                        # 切换到 ReportView,把 stream 收起来
                        await self.app.push_screen(
                            ReportScreen(final_report, event.get("metadata"))
                        )
                    return
                
                elif etype == "permission_required":
                    await self._handle_permission(event)
                
                elif etype == "plan_review":
                    await self._handle_plan_review(event)
                
                elif etype == "error":
                    stream.append_error(event["error"])
                    return
        
        except Exception as e:
            stream.append_error(f"流处理异常: {e}")
    
    async def _handle_permission(self, event: dict) -> None:
        from athena_cli.screens.permission import PermissionModal
        decision = await self.app.push_screen_wait(
            PermissionModal(event)
        )
        await self.app.client.send_permission_decision(
            event["request_id"], decision
        )
    
    async def _handle_plan_review(self, event: dict) -> None:
        from athena_cli.screens.plan_review import PlanReviewModal
        result = await self.app.push_screen_wait(
            PlanReviewModal(event["plan"])
        )
        await self.app.client.send_plan_decision(self.task_id, result)
    
    async def action_abort(self) -> None:
        """Esc:中断任务"""
        if self._aborted:
            return
        self._aborted = True
        await self.app.client.interrupt_task(self.task_id)
        self.query_one("#stream-pane", StreamPane).append_system_msg(
            "[yellow]⏸️  已请求停止...[/]"
        )
    
    async def on_unmount(self) -> None:
        if self._stream_task:
            self._stream_task.cancel()