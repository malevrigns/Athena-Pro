"""Home 屏 · 输入问题"""
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, TextArea, Button, Static


WELCOME = """
                        ╭─────────────────────╮
                        │    Athena · v1.0    │
                        ╰─────────────────────╯
                
            提一个具体的研究问题。Athena 会拆解、并行调研、
            事实核证,产出带引用的报告。
"""


class HomeScreen(Screen):
    """首屏"""
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Center():
            with Vertical(id="home-box"):
                yield Static(WELCOME, id="welcome")
                yield TextArea(
                    "",
                    id="question-input",
                    show_line_numbers=False,
                    soft_wrap=True,
                )
                yield Static("", id="error-msg")
                with Center():
                    yield Button("开始研究 [Enter]", id="submit-btn",
                                 variant="primary")
        yield Footer()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-btn":
            await self._submit()
    
    async def on_key(self, event) -> None:
        if event.key == "enter" and event.ctrl:
            await self._submit()
    
    async def _submit(self) -> None:
        text_area = self.query_one("#question-input", TextArea)
        question = text_area.text.strip()
        
        if len(question) < 10:
            self.query_one("#error-msg", Static).update(
                "[red]请输入至少 10 个字的问题[/]"
            )
            return
        
        try:
            resp = await self.app.client.create_task(question)
            self.app.current_task_id = resp["task_id"]
            # 切到任务屏(下一章实现)
            from athena_cli.screens.task import TaskScreen
            await self.app.push_screen(TaskScreen(resp["task_id"]))
        except Exception as e:
            self.query_one("#error-msg", Static).update(
                f"[red]请求失败:{e}[/]"
            )