"""Paper comparison matrix artifact (roadmap section 6.2).

The matrix is a projection over a project's papers and their latest reading
note — it owns no table of its own. It is exportable three ways: as SQLite-
backed rows (the `PaperMatrixRow` models), as a JSON artifact (`model_dump`),
and as a spreadsheet-safe CSV (`paper_matrix_to_csv`).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from athena.api.csv_utils import escape_csv_cell
from athena.research.domain import Paper, PaperNote
from athena.research.persistence import ResearchRepository

# Column order shared by the JSON rows and the CSV export.
_CSV_COLUMNS: tuple[str, ...] = (
    "paper_id",
    "title",
    "year",
    "venue",
    "screening_status",
    "problem",
    "method",
    "datasets",
    "metrics",
    "reported_score",
    "baselines",
    "code_url",
    "limitations",
    "relevance_score",
    "reproducibility_score",
)
_REPORTED_SCORE_MAX = 240


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaperMatrixRow(BaseModel):
    """One row of the comparison matrix: a paper joined with its reading note."""

    paper_id: str
    title: str
    year: int | None = None
    venue: str | None = None
    screening_status: str
    problem: str | None = None
    method: str | None = None
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    reported_score: str | None = None
    baselines: list[str] = Field(default_factory=list)
    code_url: str | None = None
    limitations: str | None = None
    relevance_score: float | None = None
    reproducibility_score: float = 0.0


class PaperMatrix(BaseModel):
    project_id: str
    row_count: int
    rows: list[PaperMatrixRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utcnow)


async def build_paper_matrix(repository: ResearchRepository, project_id: str) -> PaperMatrix:
    """Build the comparison matrix for every paper in a project."""

    papers = await repository.list_project_papers(project_id, limit=500)
    rows: list[PaperMatrixRow] = []
    for paper in papers:
        notes = await repository.list_paper_notes(paper.id)
        rows.append(_row(paper, notes[0] if notes else None))
    return PaperMatrix(project_id=project_id, row_count=len(rows), rows=rows)


def paper_matrix_to_csv(matrix: PaperMatrix) -> str:
    """Render the matrix as CSV with spreadsheet formula-injection escaping."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)
    for row in matrix.rows:
        record = row.model_dump(mode="json")
        writer.writerow([escape_csv_cell(_csv_cell(record[name])) for name in _CSV_COLUMNS])
    return buffer.getvalue()


def _row(paper: Paper, note: PaperNote | None) -> PaperMatrixRow:
    datasets = (note.datasets if note and note.datasets else paper.dataset_mentions) or []
    return PaperMatrixRow(
        paper_id=paper.id,
        title=paper.title,
        year=paper.year,
        venue=paper.venue,
        screening_status=paper.screening_status.value,
        problem=note.problem if note else None,
        method=note.method if note else None,
        datasets=list(datasets),
        metrics=list(note.metrics) if note else [],
        reported_score=_truncate(note.main_results) if note else None,
        baselines=list(note.baselines) if note else [],
        code_url=paper.code_url,
        limitations=note.limitations if note else None,
        relevance_score=paper.relevance_score,
        reproducibility_score=_reproducibility_score(paper, note, datasets),
    )


def _reproducibility_score(paper: Paper, note: PaperNote | None, datasets: list[str]) -> float:
    """Heuristic 0-1 score: code availability, repro notes and named datasets."""

    score = 0.0
    if paper.code_url:
        score += 0.4
    if note and note.reproducibility_notes:
        score += 0.3
    if datasets:
        score += 0.3
    return round(min(score, 1.0), 2)


def _truncate(text: str | None) -> str | None:
    if not text:
        return None
    collapsed = " ".join(text.split())
    if len(collapsed) <= _REPORTED_SCORE_MAX:
        return collapsed
    return collapsed[: _REPORTED_SCORE_MAX - 1].rstrip() + "…"


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)
