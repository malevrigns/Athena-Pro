"""暴露给 Agent 的工具"""
from langchain_core.tools import tool
from athena.skills.registry import get_registry
from athena.skills.loader import (
    format_skill_for_context,
    list_available_skills_summary,
    mark_loaded,
)


@tool
def list_skills() -> str:
    """列出当前可用的所有 Skill(领域知识包)。
    
    每个 skill 是一个领域的最佳实践包,包含工作流程、参考资料、辅助脚本。
    返回 skill 名称和简介。要使用某个 skill,调 load_skill(name)。
    """
    return list_available_skills_summary()


@tool
def load_skill(name: str) -> str:
    """加载指定 Skill 的详细内容到当前会话。
    
    Args:
        name: skill 的名称(从 list_skills 拿)
    
    返回 SKILL.md 全文,包含该领域的标准工作流和最佳实践。
    """
    registry = get_registry()
    skill = registry.get(name)
    if skill is None:
        available = ", ".join(s.name for s in registry.all_skills()) or "(无)"
        return f"❌ Skill '{name}' 不存在。可用 skill: {available}"
    
    mark_loaded(name)
    return format_skill_for_context(skill)


# 给 Agent 工具列表用
SKILL_TOOLS = [list_skills, load_skill]