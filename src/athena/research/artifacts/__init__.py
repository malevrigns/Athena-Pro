"""Research OS artifact layer: structured, exportable research products.

Phase 4 introduces the paper comparison matrix; later phases add taxonomy,
baseline and experiment artifacts alongside it.
"""

from __future__ import annotations

from .paper_matrix import PaperMatrix, PaperMatrixRow, build_paper_matrix, paper_matrix_to_csv

__all__ = [
    "PaperMatrix",
    "PaperMatrixRow",
    "build_paper_matrix",
    "paper_matrix_to_csv",
]
