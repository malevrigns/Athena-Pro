"""
主图构建。Athena 系统的总装现场。
"""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START

from athena.agents.planner import planner_node
from athena.agents.researcher import researcher_node
from athena.agents.supervisor import supervisor_node
from athena.agents.reviewer import reviewer_node
from athena.agents.writer import writer_node
from athena.agents.hitl import human_review_node      # 第 25 章
from athena.graph.subgraphs import (
    build_fact_checker_subgraph,
    build_citation_validator_subgraph,
)
from athena.state.schemas import ResearchState, RuntimeContext


def _wrap_subgraph_for_main(subgraph, input_key: str, output_keys: list[str]):
    """把子图包装成主图节点。
    
    子图的 state schema 和主图不同,需要做 input/output 转换。
    """
    async def node(state: ResearchState):
        # 提取子图需要的输入
        sub_input = {input_key: state.get(input_key, [])}
        # 跑子图
        result = await subgraph.ainvoke(sub_input)
        # 把子图产出的字段同步到主图(reducer 自动合并)
        return {k: result.get(k, []) for k in output_keys}
    return node


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """组装 Athena 主图。"""
    builder = StateGraph(
        ResearchState,
        context_schema=RuntimeContext,    # 1.1 新机制
    )
    
    # —— 一级节点 ——
    builder.add_node("planner", planner_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("writer", writer_node)
    
    # —— 子图节点(关键复用)——
    builder.add_node(
        "fact_checker_subgraph",
        _wrap_subgraph_for_main(
            build_fact_checker_subgraph(),
            input_key="findings",
            output_keys=["disputed"],
        ),
    )
    builder.add_node(
        "citation_validator_subgraph",
        _wrap_subgraph_for_main(
            build_citation_validator_subgraph(),
            input_key="findings",
            output_keys=["issues"],
        ),
    )
    
    # —— 入口 ——
    builder.add_edge(START, "planner")
    
    # —— 其他所有路由 ——
    # 全部由各节点的 Command(goto=...) 处理,不需要 add_edge / add_conditional_edges
    
    return builder.compile(checkpointer=checkpointer)