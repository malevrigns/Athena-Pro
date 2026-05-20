from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    autonomy_level: str
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]


AGENT_PROFILES: dict[str, AgentProfile] = {
    "planner": AgentProfile(
        "plan_generator",
        ("task_decomposition", "search_strategy", "success_criteria_design"),
        ("plan_schema",),
    ),
    "review": AgentProfile(
        "human_gate",
        ("scope_review", "approval_capture", "audit_trail"),
        ("review_decision_store", "audit_log"),
    ),
    "supervisor": AgentProfile(
        "orchestrator",
        ("route_selection", "iteration_control", "state_handoff"),
        ("runtime_state", "event_bus"),
    ),
    "researcher": AgentProfile(
        "tool_user",
        ("knowledge_retrieval", "web_search", "evidence_extraction", "source_ranking"),
        ("knowledge_base", "search_provider", "finding_schema"),
    ),
    "quality": AgentProfile(
        "validator",
        ("fact_checking", "coverage_scoring", "citation_integrity_check", "risk_scoring"),
        ("fact_checker", "quality_score"),
    ),
    "reviewer": AgentProfile(
        "critic",
        ("gap_analysis", "followup_topic_generation", "review_note_generation"),
        ("review_prompt", "plan_expander"),
    ),
    "writer": AgentProfile(
        "report_generator",
        ("synthesis", "citation_composition", "markdown_generation"),
        ("report_builder", "citation_formatter"),
    ),
}

NEXT_ACTIONS: dict[str, dict[str, str]] = {
    "planner": {
        "done": "交给 Plan Review 审批",
        "running": "继续拆解研究主题",
        "queued": "等待任务进入规划阶段",
    },
    "review": {
        "done": "交给 Supervisor 调度",
        "running": "等待人工或自动审批",
        "queued": "等待 Planner 产出计划",
    },
    "supervisor": {
        "done": "调度结果已进入下游节点",
        "running": "继续选择下一跳 Agent",
        "queued": "等待计划审批完成",
    },
    "researcher": {
        "done": "交给 Quality Gate 校验",
        "running": "继续检索知识库和外部来源",
        "queued": "等待 Supervisor 分派主题",
        "skipped": "未执行该主题研究",
    },
    "quality": {
        "done": "交给 Reviewer 或 Writer",
        "running": "继续校验来源和事实一致性",
        "queued": "等待 Researcher 产出 finding",
    },
    "reviewer": {
        "done": "补充建议已回传 Supervisor",
        "skipped": "质量达标，无需补充审阅",
        "queued": "等待 Quality Gate 判断是否需要审阅",
    },
    "writer": {
        "done": "最终报告已生成",
        "running": "继续合成报告和引用",
        "queued": "等待质量门通过",
    },
}


def profile_for(role: str) -> AgentProfile:
    return AGENT_PROFILES.get(role, AgentProfile("unknown", (), ()))


def next_action_for(role: str, status: str) -> str:
    return NEXT_ACTIONS.get(role, {}).get(status, "等待上游状态更新")
