"""Paper Reader node service.

This module owns the reusable paper-reading behavior: prompt assembly, LLM
execution, structured JSON parsing, conservative fallback extraction, and
PaperNote persistence. API routes and ToolRouter specs should call this service
instead of duplicating extraction logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecoder
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from athena.llm_factory import LLMClient, get_llm
from athena.research.domain import Paper, PaperNote, ResearchProject
from athena.research.persistence import ResearchRepository
from athena.research.prompt_assets import load_research_node_prompt

PaperTextBoundaryRule = tuple[str, str]
_PAPER_TEXT_BOUNDARY_RULES: tuple[PaperTextBoundaryRule, ...] = (
    ("abstract", "abstract"),
    ("url", "url"),
    ("pdf_url", "pdf_url"),
    ("code_url", "code_url"),
    ("dataset_mentions", "dataset_mentions"),
)


class PaperNoteDraft(BaseModel):
    """LLM-facing draft schema for a PaperNote."""

    problem: str | None = None
    method: str | None = None
    training_setup: str | None = None
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    main_results: str | None = None
    limitations: str | None = None
    reproducibility_notes: str | None = None
    important_sections: list[str] = Field(default_factory=list)

    @field_validator("datasets", "metrics", "baselines", "important_sections", mode="before")
    @classmethod
    def _normalize_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @field_validator(
        "problem",
        "method",
        "training_setup",
        "main_results",
        "limitations",
        "reproducibility_notes",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class PaperNoteExtractionPayload(BaseModel):
    project_id: str
    paper_id: str
    note: PaperNote
    extraction_source: Literal["llm_json", "fallback"]
    prompt_word_count: int
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class PaperNoteExtraction:
    note: PaperNote
    extraction_source: Literal["llm_json", "fallback"]
    prompt_word_count: int
    model: str
    input_tokens: int
    output_tokens: int

    def to_tool_payload(self, *, project_id: str, paper_id: str) -> dict[str, Any]:
        return PaperNoteExtractionPayload(
            project_id=project_id,
            paper_id=paper_id,
            note=self.note,
            extraction_source=self.extraction_source,
            prompt_word_count=self.prompt_word_count,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        ).model_dump(mode="json")


async def extract_paper_note(
    repository: ResearchRepository,
    *,
    project_id: str,
    paper_id: str,
    llm: LLMClient | None = None,
) -> PaperNoteExtraction:
    """Extract and persist one structured PaperNote for a project paper."""

    project, paper = await _load_project_paper(repository, project_id, paper_id)
    prompt_asset = load_research_node_prompt("paper_reader")
    prompt = build_paper_reader_prompt(prompt_asset.text, project=project, paper=paper)
    client = llm or get_llm("paper_reader")
    result = await client.complete_full(prompt, node="paper_reader")
    draft = _parse_note_draft(result.text)
    extraction_source: Literal["llm_json", "fallback"] = "llm_json"
    if draft is None:
        draft = _fallback_note_draft(paper)
        extraction_source = "fallback"

    note = _note_from_draft(paper.id, draft)
    await repository.create_paper_note(note)
    return PaperNoteExtraction(
        note=note,
        extraction_source=extraction_source,
        prompt_word_count=prompt_asset.word_count,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


def build_paper_reader_prompt(prompt_asset: str, *, project: ResearchProject, paper: Paper) -> str:
    """Build the full runtime prompt while keeping the long operating prompt external."""

    runtime_input = {
        "project": project.model_dump(mode="json"),
        "paper": paper.model_dump(mode="json"),
        "available_text_boundary": _available_text_boundary(paper),
        "required_output": PaperNoteDraft.model_json_schema(),
    }
    return (
        f"{prompt_asset}\n\n"
        "## Runtime Input\n\n"
        "The following JSON is the complete evidence boundary for this run unless a "
        "separate tool observation is explicitly supplied by the runtime.\n\n"
        f"```json\n{json.dumps(runtime_input, ensure_ascii=False, indent=2)}\n```\n\n"
        "Return only one JSON object matching the required_output schema. Do not wrap "
        "the JSON in Markdown fences. Do not include commentary outside the JSON."
    )


async def _load_project_paper(
    repository: ResearchRepository,
    project_id: str,
    paper_id: str,
) -> tuple[ResearchProject, Paper]:
    project = await repository.get_project(project_id)
    if project is None:
        raise LookupError("project not found")
    paper = await repository.get_paper(paper_id)
    if paper is None or paper.project_id != project_id:
        raise LookupError("paper not found")
    return project, paper


def _parse_note_draft(text: str) -> PaperNoteDraft | None:
    data = _extract_json_object(text)
    if data is None:
        return None
    try:
        return PaperNoteDraft.model_validate(data)
    except Exception:
        return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    decoder = JSONDecoder()
    starts = [0] if stripped.startswith("{") else []
    starts.extend(index for index, char in enumerate(stripped) if char == "{")
    for start in starts:
        try:
            value, _ = decoder.raw_decode(stripped[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _fallback_note_draft(paper: Paper) -> PaperNoteDraft:
    visible_sections = [
        section
        for section, field_name in (("metadata", "title"), ("abstract", "abstract"), ("code_url", "code_url"))
        if getattr(paper, field_name)
    ]

    limitations = [
        "Full paper text was not available to this node; extraction is limited to metadata"
        + (" and abstract." if paper.abstract else "."),
    ]
    if not paper.abstract:
        limitations.append("No abstract was available, so method and result details are not reported.")

    reproducibility = [
        "Abstract-only or metadata-only extraction; verify the PDF before using this note for baseline selection.",
    ]
    reproducibility.append(_code_availability_note(paper))

    return PaperNoteDraft(
        problem=paper.abstract or f"Problem statement is not reported in the available metadata for {paper.title}.",
        method=paper.abstract or "Method details are not reported in the available metadata.",
        training_setup="Training or evaluation setup is not reported in the available metadata.",
        datasets=list(paper.dataset_mentions),
        metrics=[],
        baselines=[],
        main_results="Main results are not reported in the available metadata.",
        limitations=" ".join(limitations),
        reproducibility_notes=" ".join(reproducibility),
        important_sections=visible_sections,
    )


def _note_from_draft(paper_id: str, draft: PaperNoteDraft) -> PaperNote:
    return PaperNote(
        paper_id=paper_id,
        problem=draft.problem,
        method=draft.method,
        training_setup=draft.training_setup,
        datasets=draft.datasets,
        metrics=draft.metrics,
        baselines=draft.baselines,
        main_results=draft.main_results,
        limitations=draft.limitations,
        reproducibility_notes=draft.reproducibility_notes,
        important_sections=draft.important_sections,
    )


def _available_text_boundary(paper: Paper) -> list[str]:
    visible = [
        label
        for label, field_name in _PAPER_TEXT_BOUNDARY_RULES
        if getattr(paper, field_name)
    ]
    return ["metadata", *visible]


def _code_availability_note(paper: Paper) -> str:
    if paper.code_url:
        return f"Code URL is present and should be inspected separately: {paper.code_url}"
    return "No code URL is recorded on the paper asset."
