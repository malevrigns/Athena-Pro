"""Tests for the PaperMatrix artifact (roadmap section 6.2)."""

from __future__ import annotations

import csv
import io

import pytest

from athena.research.artifacts import build_paper_matrix, paper_matrix_to_csv
from athena.research.domain import Paper, PaperNote, ResearchProject


@pytest.mark.asyncio
async def test_build_paper_matrix_joins_papers_with_latest_note(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    with_note = Paper(
        project_id=project.id,
        title="Retrieval-Augmented Generation",
        year=2020,
        venue="NeurIPS",
        code_url="https://github.com/example/rag",
        relevance_score=0.9,
    )
    bare = Paper(project_id=project.id, title="Bare paper")
    await repo.create_paper(with_note)
    await repo.create_paper(bare)
    await repo.create_paper_note(
        PaperNote(
            paper_id=with_note.id,
            problem="Knowledge-intensive QA",
            method="Retriever plus generator",
            datasets=["Natural Questions"],
            metrics=["exact match"],
            baselines=["closed-book T5"],
            main_results="EM improves by 3 points",
            reproducibility_notes="configs released",
        )
    )

    matrix = await build_paper_matrix(repo, project.id)

    assert matrix.row_count == 2
    rows = {row.paper_id: row for row in matrix.rows}
    rich = rows[with_note.id]
    assert rich.method == "Retriever plus generator"
    assert rich.datasets == ["Natural Questions"]
    assert rich.baselines == ["closed-book T5"]
    # code_url + repro notes + datasets -> full reproducibility score.
    assert rich.reproducibility_score == 1.0
    # a paper with no note and no signals scores zero.
    assert rows[bare.id].reproducibility_score == 0.0
    assert rows[bare.id].method is None


@pytest.mark.asyncio
async def test_paper_matrix_csv_has_header_and_escapes_formula_cells(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="RAG", research_question="Q?")
    await repo.create_project(project)
    # a title that starts with '=' would be a spreadsheet formula injection.
    await repo.create_paper(
        Paper(project_id=project.id, title="=cmd|' /c calc'!A1", year=2024)
    )

    matrix = await build_paper_matrix(repo, project.id)
    rendered = paper_matrix_to_csv(matrix)

    parsed = list(csv.reader(io.StringIO(rendered)))
    assert parsed[0][:3] == ["paper_id", "title", "year"]
    title_cell = parsed[1][parsed[0].index("title")]
    assert title_cell.startswith("'=")


@pytest.mark.asyncio
async def test_empty_project_paper_matrix_is_valid(make_store):
    repo = await make_store().research_repository()
    project = ResearchProject(title="empty", research_question="Q?")
    await repo.create_project(project)

    matrix = await build_paper_matrix(repo, project.id)

    assert matrix.row_count == 0
    assert matrix.rows == []
    # header row is still emitted for an empty matrix.
    assert paper_matrix_to_csv(matrix).strip().startswith("paper_id,title,year")
