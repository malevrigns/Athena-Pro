from __future__ import annotations

from athena.llm_factory import _system_prompt
from athena.research.prompt_assets import (
    MIN_RESEARCH_NODE_PROMPT_WORDS,
    RESEARCH_NODE_PROMPT_FILES,
    list_research_node_prompt_keys,
    load_research_node_prompt,
)


def test_all_registered_research_node_prompts_are_production_length():
    assert len(RESEARCH_NODE_PROMPT_FILES) >= 18
    assert len(set(RESEARCH_NODE_PROMPT_FILES.values())) == len(RESEARCH_NODE_PROMPT_FILES)

    for node_key in list_research_node_prompt_keys():
        asset = load_research_node_prompt(node_key)
        assert asset.path.exists()
        assert asset.word_count >= MIN_RESEARCH_NODE_PROMPT_WORDS
        assert asset.node_key == node_key


def test_runtime_system_prompt_uses_long_node_prompt_asset():
    prompt = _system_prompt("planner")

    assert "# Planner Agent Prompt" in prompt
    assert len(prompt.split()) >= MIN_RESEARCH_NODE_PROMPT_WORDS


def test_unknown_runtime_node_keeps_legacy_fallback_prompt():
    prompt = _system_prompt("unknown_node")

    assert "Athena Pro" in prompt
    assert len(prompt.split()) < MIN_RESEARCH_NODE_PROMPT_WORDS
