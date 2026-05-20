"""terminal 里的节点流程图"""
from __future__ import annotations
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.console import RenderableType


# 节点拓扑(同 web 端)
NODES = [
    ("planner",            "Planner",     0, 1),
    ("plan_review",        "PlanReview",  1, 1),
    ("supervisor",         "Supervisor",  2, 1),
    ("researcher",         "Researcher",  3, 0),
    ("fact_check",         "FactCheck",   3, 1),
    ("citation_validator", "Citation",    3, 2),
    ("writer",             "Writer",      4, 1),
    ("reviewer",           "Reviewer",    5, 1),
]

EDGES = [
    ("planner", "plan_review"),
    ("plan_review", "supervisor"),
    ("supervisor", "researcher"),
    ("supervisor", "fact_check"),
    ("supervisor", "citation_validator"),
    ("researcher", "writer"),
    ("fact_check", "writer"),
    ("citation_validator", "writer"),
    ("writer", "reviewer"),
]


class FlowGraphWidget(Widget):
    """节点状态图,ASCII 渲染。reactive 让状态变化自动 re-render。"""
    
    statuses: reactive[dict[str, str]] = reactive(dict, recompose=False)
    
    def set_node_status(self, node_id: str, status: str) -> None:
        """status: pending | running | done | failed"""
        new = dict(self.statuses)
        new[node_id] = status
        self.statuses = new
    
    def render(self) -> RenderableType:
        text = Text()
        # 简化版 ASCII 渲染:每行一个节点
        for node_id, label, row, col in NODES:
            status = self.statuses.get(node_id, "pending")
            marker = {
                "pending": "○",
                "running": "◐",
                "done":    "●",
                "failed":  "✗",
            }[status]
            color = {
                "pending": "grey50",
                "running": "yellow bold",
                "done":    "green bold",
                "failed":  "red bold",
            }[status]
            
            # 缩进表示层级
            indent = "  " * col
            text.append(f"{indent}{marker} ", style=color)
            text.append(f"{label}\n",
                        style=("bold" if status == "running" else ""))
        return text