from __future__ import annotations

import re
from pathlib import Path

from athena.research.events import RESEARCH_EVENT_TYPES


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SCHEMA = ROOT / "web/src/types/researchEvents.ts"


def _source() -> str:
    return FRONTEND_SCHEMA.read_text(encoding="utf-8")


def test_frontend_research_event_schema_exists():
    assert FRONTEND_SCHEMA.exists()


def test_frontend_research_event_types_match_backend():
    source = _source()
    literals = set(re.findall(r"type:\s*z\.literal\('([^']+)'\)", source))

    assert literals == set(RESEARCH_EVENT_TYPES)
    assert "z.discriminatedUnion('type'" in source


def test_frontend_research_event_type_constant_matches_backend():
    source = _source()
    match = re.search(
        r"export const RESEARCH_EVENT_TYPES = \[(.*?)\] as const",
        source,
        re.DOTALL,
    )
    assert match is not None
    listed = set(re.findall(r"'([^']+)'", match.group(1)))

    assert listed == set(RESEARCH_EVENT_TYPES)


def test_frontend_research_event_payload_schemas_are_explicit():
    source = _source()
    for schema_name in [
        "StatusPayload",
        "PlanReviewRequiredPayload",
        "ToolCallPayload",
        "ToolObservationPayload",
        "PaperFoundPayload",
        "ClaimExtractedPayload",
        "ArtifactCreatedPayload",
        "ErrorPayload",
        "DonePayload",
    ]:
        assert f"export const {schema_name} = z.object" in source

    assert "payload: z.record" not in source
    assert "structured_output: AnyRecord.default(() => ({}))" in source

