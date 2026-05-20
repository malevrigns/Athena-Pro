"""扫描磁盘上的 skills 目录,索引所有 SKILL.md"""
from __future__ import annotations
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator
import structlog

logger = structlog.get_logger()


@dataclass
class SkillMetadata:
    """SKILL.md 的 frontmatter + 路径信息"""
    name: str
    description: str
    version: str = "0.0.1"
    author: str = "unknown"
    when_to_use: list[str] = field(default_factory=list)
    requires_tools: list[str] = field(default_factory=list)
    
    # 磁盘位置
    skill_dir: Path = field(default_factory=Path)
    skill_md_path: Path = field(default_factory=Path)
    
    def full_content(self) -> str:
        """返回完整 SKILL.md 内容(给 LLM load 时用)"""
        return self.skill_md_path.read_text(encoding="utf-8")
    
    def list_references(self) -> list[Path]:
        """列出 reference/ 下所有文件"""
        ref_dir = self.skill_dir / "reference"
        if not ref_dir.exists():
            return []
        return sorted(p for p in ref_dir.rglob("*") if p.is_file())
    
    def list_scripts(self) -> list[Path]:
        scripts_dir = self.skill_dir / "scripts"
        if not scripts_dir.exists():
            return []
        return sorted(p for p in scripts_dir.rglob("*") if p.is_file())


class SkillRegistry:
    """全局 skill 注册表。启动时扫描,提供按 name 查找。"""
    
    def __init__(self, skill_dirs: list[Path]):
        self.skill_dirs = skill_dirs
        self._skills: dict[str, SkillMetadata] = {}
        self.reload()
    
    def reload(self) -> None:
        """重新扫描所有 skill 目录"""
        self._skills.clear()
        for dir_ in self.skill_dirs:
            if not dir_.exists():
                logger.warning("skill_dir_not_found", path=str(dir_))
                continue
            for skill_md in dir_.glob("*/SKILL.md"):
                try:
                    meta = self._parse_skill_md(skill_md)
                    if meta.name in self._skills:
                        logger.warning(
                            "duplicate_skill_name",
                            name=meta.name,
                            existing=str(self._skills[meta.name].skill_dir),
                            new=str(meta.skill_dir),
                        )
                    self._skills[meta.name] = meta
                    logger.info("skill_loaded", name=meta.name, dir=str(meta.skill_dir))
                except Exception as e:
                    logger.exception("skill_parse_failed", path=str(skill_md), error=str(e))
    
    @staticmethod
    def _parse_skill_md(path: Path) -> SkillMetadata:
        """解析 SKILL.md 的 YAML frontmatter"""
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            raise ValueError(f"SKILL.md missing frontmatter: {path}")
        
        # 切出 frontmatter 块
        end = content.find("\n---", 4)
        if end == -1:
            raise ValueError(f"unclosed frontmatter: {path}")
        
        frontmatter_yaml = content[4:end]
        meta_dict = yaml.safe_load(frontmatter_yaml) or {}
        
        return SkillMetadata(
            name=meta_dict.get("name", path.parent.name),
            description=meta_dict.get("description", ""),
            version=meta_dict.get("version", "0.0.1"),
            author=meta_dict.get("author", "unknown"),
            when_to_use=meta_dict.get("when_to_use", []) or [],
            requires_tools=meta_dict.get("requires_tools", []) or [],
            skill_dir=path.parent,
            skill_md_path=path,
        )
    
    def get(self, name: str) -> SkillMetadata | None:
        return self._skills.get(name)
    
    def all_skills(self) -> list[SkillMetadata]:
        return sorted(self._skills.values(), key=lambda s: s.name)
    
    def __len__(self) -> int:
        return len(self._skills)


# 全局单例
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        from athena.config import settings
        dirs = [Path(d).expanduser() for d in settings.skills_dirs]
        _registry = SkillRegistry(skill_dirs=dirs)
    return _registry