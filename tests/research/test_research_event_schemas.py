"""Tests for the Research OS typed event protocol (Phase 1, step 3)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import get_args

import pytest
from pydantic import ValidationError

from athena.research.domain import Claim, Paper
from athena.research.events import (
    RESEARCH_EVENT_ADAPTER,
    RESEARCH_EVENT_TYPES,
    ClaimExtractedEvent,
    PaperFoundEvent,
    ResearchEvent,
    StatusEvent,
    StatusPayload,
    ToolCallEvent,
    ToolCallPayload,
    ToolObservationPayload,
)

# One valid raw event dict per supported event type.
VALID_EVENTS: dict[str, dict] = {
    "status": {
        "type": "status",
        "task_id": "t1",
        "payload": {"status": "planning", "message": "drafting plan"},
    },
    "plan_review_required": {
        "type": "plan_review_required",
        "task_id": "t1",
        "payload": {
            "checkpoint_id": "ck1",
            "title": "Approve research plan",
            "plan": {"topics": ["rag", "eval"]},
            "risk_level": "low",
            "estimated_cost_usd": 0.42,
        },
    },
    "tool_call": {
        "type": "tool_call",
        "task_id": "t1",
        "payload": {
            "tool_call_id": "tc1",
            "tool_name": "paper_search",
            "arguments": {"query": "retrieval augmented generation"},
        },
    },
    "tool_observation": {
        "type": "tool_observation",
        "task_id": "t1",
        "payload": {
            "tool_call_id": "tc1",
            "status": "ok",
            "summary": "found 3 papers",
        },
    },
    "paper_found": {
        "type": "paper_found",
        "task_id": "t1",
        "payload": {"paper": {"project_id": "p1", "title": "Attention Is All You Need"}},
    },
    "claim_extracted": {
        "type": "claim_extracted",
        "task_id": "t1",
        "payload": {
            "claim": {"project_id": "p1", "text": "X beats Y", "claim_type": "result"}
        },
    },
    "artifact_created": {
        "type": "artifact_created",
        "task_id": "t1",
        "payload": {"artifact_id": "a1", "artifact_type": "code", "path": "train.py"},
    },
    "error": {
        "type": "error",
        "task_id": "t1",
        "payload": {"message": "search failed", "code": "E_NET"},
    },
    "done": {
        "type": "done",
        "task_id": "t1",
        "payload": {"summary": "research complete"},
    },
}


# --- validation across all event types -----------------------------------


@pytest.mark.parametrize("type_name", sorted(RESEARCH_EVENT_TYPES))
def test_every_event_type_validates(type_name):
    event = RESEARCH_EVENT_ADAPTER.validate_python(VALID_EVENTS[type_name])
    assert event.type == type_name
    assert event.task_id == "t1"
    assert event.seq == 0
    assert event.project_id is None


def test_invalid_event_type_fails_validation():
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {"type": "totally_unknown", "task_id": "t1", "payload": {}}
        )


def test_missing_required_payload_field_fails_validation():
    # status payload requires `status`
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {"type": "status", "task_id": "t1", "payload": {}}
        )
    # tool_call payload requires tool_call_id / tool_name / arguments
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {"type": "tool_call", "task_id": "t1", "payload": {"tool_name": "x"}}
        )
    # error payload requires `message`
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {"type": "error", "task_id": "t1", "payload": {"code": "E"}}
        )


def test_missing_required_envelope_field_fails_validation():
    # task_id is required
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {"type": "status", "payload": {"status": "ok"}}
        )
    # payload is required
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python({"type": "status", "task_id": "t1"})


# --- payload-specific behavior -------------------------------------------


def test_tool_call_arguments_and_defaults():
    # `arguments` is required (no default)
    with pytest.raises(ValidationError):
        ToolCallPayload(tool_call_id="tc1", tool_name="paper_search")

    args = {"query": "retrieval augmented generation", "limit": 5}
    payload = ToolCallPayload(
        tool_call_id="tc1", tool_name="paper_search", arguments=args
    )
    assert payload.arguments == args
    assert payload.approval_required is False
    assert payload.permission_level is None

    # arguments survive a round-trip through the adapter
    event = ToolCallEvent(task_id="t1", payload=payload)
    restored = RESEARCH_EVENT_ADAPTER.validate_python(event.model_dump(mode="json"))
    assert isinstance(restored, ToolCallEvent)
    assert restored.payload.arguments == args
    assert restored.payload.approval_required is False


def test_tool_observation_structured_output_defaults_are_isolated():
    a = ToolObservationPayload(tool_call_id="tc1", status="ok", summary="s")
    b = ToolObservationPayload(tool_call_id="tc2", status="ok", summary="s")
    assert a.structured_output == {} and b.structured_output == {}
    assert a.structured_output is not b.structured_output  # not a shared default
    a.structured_output["leaked"] = True
    assert b.structured_output == {}


def test_paper_found_validates_nested_paper():
    event = RESEARCH_EVENT_ADAPTER.validate_python(VALID_EVENTS["paper_found"])
    assert isinstance(event, PaperFoundEvent)
    assert isinstance(event.payload.paper, Paper)
    assert event.payload.paper.title == "Attention Is All You Need"

    # an invalid nested Paper (missing required `title`) fails validation
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {
                "type": "paper_found",
                "task_id": "t1",
                "payload": {"paper": {"project_id": "p1"}},
            }
        )


def test_claim_extracted_validates_nested_claim():
    event = RESEARCH_EVENT_ADAPTER.validate_python(VALID_EVENTS["claim_extracted"])
    assert isinstance(event, ClaimExtractedEvent)
    assert isinstance(event.payload.claim, Claim)
    assert event.payload.claim.claim_type == "result"

    # an invalid nested Claim (missing required `text`/`claim_type`) fails
    with pytest.raises(ValidationError):
        RESEARCH_EVENT_ADAPTER.validate_python(
            {
                "type": "claim_extracted",
                "task_id": "t1",
                "payload": {"claim": {"project_id": "p1"}},
            }
        )


# --- envelope behavior ---------------------------------------------------


def test_timestamp_default_is_timezone_aware_utc():
    event = StatusEvent(task_id="t1", payload=StatusPayload(status="ok"))
    assert event.timestamp.tzinfo is not None
    assert event.timestamp.utcoffset() == timedelta(0)


def test_seq_rejects_negative_values():
    with pytest.raises(ValidationError):
        StatusEvent(task_id="t1", seq=-1, payload=StatusPayload(status="ok"))
    # zero and positive values are accepted
    assert StatusEvent(task_id="t1", seq=0, payload=StatusPayload(status="ok")).seq == 0
    assert StatusEvent(task_id="t1", seq=7, payload=StatusPayload(status="ok")).seq == 7


# --- protocol-level invariants -------------------------------------------


def test_research_event_types_matches_union_members():
    union = get_args(ResearchEvent)[0]  # unwrap Annotated[Union[...], Field(...)]
    members = get_args(union)
    type_literals = {member.model_fields["type"].default for member in members}
    assert type_literals == set(RESEARCH_EVENT_TYPES)
    # the test fixtures cover exactly the supported event types
    assert set(VALID_EVENTS) == set(RESEARCH_EVENT_TYPES)


def test_model_dump_json_mode_is_json_safe():
    for type_name in RESEARCH_EVENT_TYPES:
        event = RESEARCH_EVENT_ADAPTER.validate_python(VALID_EVENTS[type_name])
        dumped = event.model_dump(mode="json")
        json.dumps(dumped)  # raises TypeError if any value is not JSON-safe
        assert dumped["type"] == type_name
        assert isinstance(dumped["timestamp"], str)
