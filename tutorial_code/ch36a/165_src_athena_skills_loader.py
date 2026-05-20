"""把 skill 加载到当前 Agent 的 context"""
from __future__ import annotations
from contextvars import ContextVar
from athena.skills.registry import get_registry, SkillMetadata


# 当前任务已加载的 skill 列表(contextvars 跟随协程)
_loaded_skills: ContextVar[list[str]] = ContextVar("loaded_skills", default=[])


def get_loaded_skills() -> list[str]:
    return _loaded_skills.get()


def mark_loaded(name: str) -> None:
    current = _loaded_skills.get().copy()
    if name not in current:
        current.append(name)
        _loaded_skills.set(current)


def reset_loaded() -> None:
    """每个新任务开始时调用,清空已加载列表"""
    _loaded_skills.set([])


def format_skill_for_context(meta: SkillMetadata) -> str:
    """格式化 SKILL.md 内容供注入 LLM context"""
    return f"""
# Skill: {meta.name}

{meta.full_content()}

---
(以上是 Skill 内容。reference/ 下还有 {len(meta.list_references())} 份参考文件,
按需用 read_file 工具读取。scripts/ 下有 {len(meta.list_scripts())} 个脚本,
用 python_repl 工具执行,路径前缀:{meta.skill_dir}/scripts/)
"""


def list_available_skills_summary() -> str:
    """给 LLM 看的简要 skill 清单(只 name + description,不含正文)"""
    registry = get_registry()
    if len(registry) == 0:
        return "(暂无可用 skill)"
    
    lines = ["可用 Skill 清单(用 load_skill(name) 加载详细内容):"]
    for skill in registry.all_skills():
        loaded = " [已加载]" if skill.name in get_loaded_skills() else ""
        lines.append(f"- **{skill.name}**{loaded}: {skill.description}")
    return "\n".join(lines)