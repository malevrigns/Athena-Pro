"""Prompt asset registry for Research OS agent nodes.

Long node prompts live in `docs/prompts/` instead of Python source so runtime
code stays readable while prompts remain auditable, versionable assets.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


MIN_RESEARCH_NODE_PROMPT_WORDS = 5000

RESEARCH_NODE_PROMPT_FILES: dict[str, str] = {
    "planner": "PLANNER_AGENT_PROMPT.md",
    "supervisor": "SUPERVISOR_NODE_PROMPT.md",
    "researcher": "RESEARCHER_AGENT_PROMPT.md",
    "paper_collector": "PAPER_COLLECTOR_AGENT_PROMPT.md",
    "paper_reader": "PAPER_READER_NOTE_NODE_PROMPT.md",
    "evidence_extractor": "EVIDENCE_EXTRACTOR_AGENT_PROMPT.md",
    "taxonomy": "TAXONOMY_AGENT_PROMPT.md",
    "baseline_selector": "BASELINE_SELECTOR_AGENT_PROMPT.md",
    "idea_generator": "IDEA_GENERATOR_AGENT_PROMPT.md",
    "code_scout": "CODE_SCOUT_AGENT_PROMPT.md",
    "reproducer": "REPRODUCER_AGENT_PROMPT.md",
    "experiment_designer": "EXPERIMENT_DESIGNER_AGENT_PROMPT.md",
    "quality_gate": "QUALITY_GATE_NODE_PROMPT.md",
    "reviewer": "REVIEWER_AGENT_PROMPT.md",
    "writer": "WRITER_AGENT_PROMPT.md",
    "citation_review": "CITATION_REVIEW_NODE_PROMPT.md",
    "plan_review": "PLAN_REVIEW_NODE_PROMPT.md",
    "baseline_review": "BASELINE_REVIEW_NODE_PROMPT.md",
    "experiment_review": "EXPERIMENT_REVIEW_NODE_PROMPT.md",
}


@dataclass(frozen=True)
class ResearchNodePromptAsset:
    node_key: str
    path: Path
    text: str

    @property
    def word_count(self) -> int:
        return count_words(self.text)

    def assert_production_ready(self) -> None:
        if self.word_count < MIN_RESEARCH_NODE_PROMPT_WORDS:
            raise ValueError(
                f"{self.node_key} prompt is too short: "
                f"{self.word_count} < {MIN_RESEARCH_NODE_PROMPT_WORDS} words"
            )


def prompt_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "prompts"


def list_research_node_prompt_keys() -> list[str]:
    return sorted(RESEARCH_NODE_PROMPT_FILES)


@lru_cache(maxsize=None)
def load_research_node_prompt(node_key: str) -> ResearchNodePromptAsset:
    try:
        filename = RESEARCH_NODE_PROMPT_FILES[node_key]
    except KeyError as exc:
        known = ", ".join(list_research_node_prompt_keys())
        raise KeyError(f"unknown research node prompt: {node_key}; known: {known}") from exc

    path = prompt_root() / filename
    text = path.read_text(encoding="utf-8")
    asset = ResearchNodePromptAsset(node_key=node_key, path=path, text=text)
    asset.assert_production_ready()
    return asset


def count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])
