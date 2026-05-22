from __future__ import annotations

import pytest

from athena.llm_factory import LLMResult
from athena.research.domain import Paper, ResearchProject
from athena.research.services.paper_reader import (
    PaperNoteDraft,
    build_paper_reader_prompt,
    extract_paper_note,
)


class FakeResearchRepository:
    def __init__(self, project: ResearchProject, paper: Paper) -> None:
        self.project = project
        self.paper = paper
        self.created_notes = []

    async def get_project(self, project_id: str):
        return self.project if project_id == self.project.id else None

    async def get_paper(self, paper_id: str):
        return self.paper if paper_id == self.paper.id else None

    async def create_paper_note(self, note):
        self.created_notes.append(note)


class JsonLLM:
    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        assert node == "paper_reader"
        assert "Return only one JSON object" in prompt
        return LLMResult(
            text="""
            {
              "problem": "evaluate retrieval-augmented generation",
              "method": "combine parametric generation with retrieved passages",
              "training_setup": "fine-tuning with supervised QA data",
              "datasets": ["Natural Questions", "TriviaQA"],
              "metrics": ["EM", "F1"],
              "baselines": ["BART", "DPR"],
              "main_results": "improves over non-retrieval baselines",
              "limitations": "full implementation details still need PDF validation",
              "reproducibility_notes": "official code should be checked before reproduction",
              "important_sections": ["abstract", "experiments"]
            }
            """,
            input_tokens=123,
            output_tokens=45,
            model="fake-json",
        )


class NonJsonLLM:
    async def complete(self, prompt: str, *, node: str) -> str:
        return (await self.complete_full(prompt, node=node)).text

    async def complete_full(self, prompt: str, *, node: str) -> LLMResult:
        return LLMResult(text="not json", input_tokens=10, output_tokens=2, model="fake-text")


@pytest.mark.asyncio
async def test_extract_paper_note_persists_llm_json_draft():
    project = ResearchProject(
        id="proj_test",
        title="RAG",
        research_question="Which RAG baseline should we reproduce?",
    )
    paper = Paper(
        id="paper_test",
        project_id=project.id,
        title="Retrieval-Augmented Generation",
        abstract="RAG combines retrieval and generation.",
    )
    repo = FakeResearchRepository(project, paper)

    extraction = await extract_paper_note(
        repo,
        project_id=project.id,
        paper_id=paper.id,
        llm=JsonLLM(),
    )

    assert extraction.extraction_source == "llm_json"
    assert extraction.prompt_word_count >= 5000
    assert extraction.model == "fake-json"
    assert extraction.note.problem == "evaluate retrieval-augmented generation"
    assert extraction.note.datasets == ["Natural Questions", "TriviaQA"]
    assert extraction.to_tool_payload(project_id=project.id, paper_id=paper.id)["note"]["id"] == extraction.note.id
    assert repo.created_notes == [extraction.note]


@pytest.mark.asyncio
async def test_extract_paper_note_falls_back_when_model_output_is_not_json():
    project = ResearchProject(
        id="proj_test",
        title="RAG",
        research_question="Which RAG baseline should we reproduce?",
    )
    paper = Paper(
        id="paper_test",
        project_id=project.id,
        title="Retrieval-Augmented Generation",
        abstract="RAG combines retrieval and generation.",
        code_url="https://github.com/example/rag",
        dataset_mentions=["Natural Questions"],
    )
    repo = FakeResearchRepository(project, paper)

    extraction = await extract_paper_note(
        repo,
        project_id=project.id,
        paper_id=paper.id,
        llm=NonJsonLLM(),
    )

    assert extraction.extraction_source == "fallback"
    assert extraction.note.problem == paper.abstract
    assert extraction.note.datasets == ["Natural Questions"]
    assert extraction.note.important_sections == ["metadata", "abstract", "code_url"]
    assert "metadata" in (extraction.note.limitations or "")
    assert "https://github.com/example/rag" in (extraction.note.reproducibility_notes or "")


def test_paper_reader_prompt_contains_runtime_input_schema():
    project = ResearchProject(
        id="proj_test",
        title="RAG",
        research_question="Which RAG baseline should we reproduce?",
    )
    paper = Paper(id="paper_test", project_id=project.id, title="RAG paper")

    prompt = build_paper_reader_prompt("long prompt", project=project, paper=paper)

    assert '"project"' in prompt
    assert '"paper"' in prompt
    assert '"required_output"' in prompt
    assert PaperNoteDraft.model_json_schema()["title"] in prompt
