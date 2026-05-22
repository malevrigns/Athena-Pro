"""Focused tests for Research OS domain models (Phase 1, step 1).

Covers: enum values, required fields, default list/dict isolation and basic
model serialization, per acceptance criteria in the Phase 1 step 1 task.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import BaseModel, ValidationError

from athena.research.domain import (
    BaselineCandidate,
    Claim,
    CodeArtifact,
    Evidence,
    ExperimentRun,
    ExperimentSpec,
    MethodTaxonomy,
    Paper,
    PaperNote,
    PaperScreeningStatus,
    ProjectStatus,
    ResearchIdea,
    ResearchProject,
    ReviewDecision,
)

# Minimal valid keyword arguments for each model: exactly its required fields.
MINIMAL: dict[type[BaseModel], dict] = {
    ResearchProject: dict(title="LLM eval", research_question="How to eval LLMs?"),
    Paper: dict(project_id="proj_1", title="Attention Is All You Need"),
    PaperNote: dict(paper_id="paper_1"),
    Claim: dict(project_id="proj_1", text="X beats Y", claim_type="result"),
    Evidence: dict(claim_id="claim_1", source_type="paper"),
    MethodTaxonomy: dict(project_id="proj_1"),
    BaselineCandidate: dict(
        project_id="proj_1", name="ResNet", method_summary="residual network"
    ),
    ResearchIdea: dict(
        project_id="proj_1",
        title="calibrated loss",
        motivation="cross-entropy is poorly calibrated",
        core_hypothesis="a calibration term improves reliability",
        method_sketch="add a temperature-scaled regulariser",
    ),
    ExperimentSpec: dict(project_id="proj_1", task="image-classification"),
    ExperimentRun: dict(experiment_spec_id="exp_1"),
    CodeArtifact: dict(project_id="proj_1", path="baselines/resnet/train.py"),
}

ALL_MODELS = list(MINIMAL)

COLLECTION_FIELDS = [
    (model, name)
    for model in ALL_MODELS
    for name, field in model.model_fields.items()
    if field.default_factory in (list, dict)
]


def build(model: type[BaseModel]) -> BaseModel:
    return model(**MINIMAL[model])


# --- enums ---------------------------------------------------------------


def test_enum_values():
    assert [s.value for s in ProjectStatus] == [
        "draft",
        "planning",
        "running",
        "waiting_review",
        "completed",
        "failed",
        "cancelled",
    ]
    assert [s.value for s in PaperScreeningStatus] == [
        "candidate",
        "included",
        "excluded",
        "read",
    ]
    assert [s.value for s in ReviewDecision] == [
        "pending",
        "approved",
        "changes_requested",
        "rejected",
    ]


def test_enums_are_str_enums():
    for member in (ProjectStatus.running, PaperScreeningStatus.read, ReviewDecision.approved):
        assert isinstance(member, str)
    assert ProjectStatus.draft == "draft"
    assert PaperScreeningStatus.candidate == "candidate"
    assert ReviewDecision.pending == "pending"


# --- construction & identity --------------------------------------------


def test_all_eleven_models_are_covered():
    assert len(ALL_MODELS) == 11


@pytest.mark.parametrize("model", ALL_MODELS)
def test_model_constructs_with_minimal_kwargs(model):
    a = build(model)
    b = build(model)
    assert isinstance(a.id, str) and a.id
    assert a.id != b.id  # unique per instance
    prefix, _, rest = a.id.partition("_")
    assert prefix and rest  # ids are prefixed, e.g. "proj_..."
    assert isinstance(a.created_at, datetime)


@pytest.mark.parametrize("model", ALL_MODELS)
def test_generated_ids_use_full_uuid_hex(model):
    """IDs keep the prefix but carry the full, untruncated uuid4 hex suffix."""
    prefix, sep, suffix = build(model).id.partition("_")
    assert prefix and sep == "_"
    assert len(suffix) == 32  # full uuid4().hex, not truncated
    assert all(c in "0123456789abcdef" for c in suffix)


# --- required fields -----------------------------------------------------


@pytest.mark.parametrize("model", ALL_MODELS)
def test_minimal_kwargs_match_required_fields(model):
    """MINIMAL must list exactly the model's required fields, no more, no less."""
    required = {n for n, f in model.model_fields.items() if f.is_required()}
    assert set(MINIMAL[model]) == required


@pytest.mark.parametrize("model", ALL_MODELS)
def test_required_fields_are_enforced(model):
    required = [n for n, f in model.model_fields.items() if f.is_required()]
    assert required, f"{model.__name__} should declare at least one required field"
    for name in required:
        kwargs = {k: v for k, v in MINIMAL[model].items() if k != name}
        with pytest.raises(ValidationError):
            model(**kwargs)


# --- default list/dict isolation -----------------------------------------


def test_collection_fields_exist():
    assert COLLECTION_FIELDS  # guards the data-driven test below


@pytest.mark.parametrize("model,name", COLLECTION_FIELDS)
def test_default_collection_is_isolated_per_instance(model, name):
    a = build(model)
    b = build(model)
    col_a, col_b = getattr(a, name), getattr(b, name)
    assert col_a is not col_b  # distinct objects, not a shared default
    assert not col_a and not col_b  # both start empty
    if isinstance(col_a, dict):
        col_a["leaked"] = True
    else:
        col_a.append("leaked")
    assert not getattr(b, name), f"{model.__name__}.{name} default leaked across instances"


# --- serialization -------------------------------------------------------


@pytest.mark.parametrize("model", ALL_MODELS)
def test_model_round_trips_through_dict_and_json(model):
    instance = build(model)
    assert model.model_validate(instance.model_dump()) == instance
    assert model.model_validate_json(instance.model_dump_json()) == instance


def test_enum_fields_serialize_to_plain_strings():
    project_json = ResearchProject(**MINIMAL[ResearchProject]).model_dump(mode="json")
    assert project_json["status"] == "draft"
    paper_json = Paper(**MINIMAL[Paper]).model_dump(mode="json")
    assert paper_json["screening_status"] == "candidate"


# --- per-model defaults --------------------------------------------------


def test_research_project_defaults():
    project = ResearchProject(title="LLM eval", research_question="How to eval?")
    assert project.status is ProjectStatus.draft
    assert project.constraints == []
    assert project.field is None
    assert project.owner is None
    assert isinstance(project.created_at, datetime)
    assert isinstance(project.updated_at, datetime)


def test_paper_defaults():
    paper = Paper(project_id="proj_1", title="Attention")
    assert paper.screening_status is PaperScreeningStatus.candidate
    assert paper.authors == []
    assert paper.dataset_mentions == []
    assert paper.relevance_score is None
    assert paper.citation_count is None


def test_paper_screening_status_accepts_enum_value():
    paper = Paper(project_id="proj_1", title="t", screening_status="included")
    assert paper.screening_status is PaperScreeningStatus.included


def test_claim_and_evidence_defaults():
    claim = Claim(project_id="proj_1", text="X beats Y", claim_type="result")
    assert claim.status == "draft"
    assert claim.evidence_ids == []
    assert claim.confidence is None
    assert claim.paper_id is None

    evidence = Evidence(claim_id=claim.id, source_type="paper", quote="see table 2")
    assert evidence.verification_status == "unchecked"
    assert evidence.normalized_text is None


def test_baseline_and_idea_defaults():
    baseline = BaselineCandidate(
        project_id="proj_1", name="ResNet", method_summary="residual network"
    )
    assert baseline.status == "candidate"
    assert baseline.rank_score is None
    assert baseline.license is None

    idea = ResearchIdea(
        project_id="proj_1",
        title="new loss",
        motivation="m",
        core_hypothesis="h",
        method_sketch="s",
    )
    assert idea.status == "candidate"
    assert idea.required_baselines == []
    assert idea.evidence_ids == []
    assert idea.overall_score is None


def test_experiment_models_defaults():
    spec = ExperimentSpec(project_id="proj_1", task="classification")
    assert spec.metrics == []
    assert spec.config == {}
    assert spec.seed_plan == []
    assert spec.ablation_plan == []

    run = ExperimentRun(experiment_spec_id=spec.id)
    assert run.status == "pending"
    assert run.started_at is None
    assert run.ended_at is None
    assert run.exit_code is None
    assert run.metrics == {}
    assert run.artifacts == []


def test_method_taxonomy_and_code_artifact_defaults():
    taxonomy = MethodTaxonomy(project_id="proj_1")
    assert taxonomy.nodes == []
    assert taxonomy.edges == []
    assert taxonomy.open_problems == []

    artifact = CodeArtifact(project_id="proj_1", path="train.py")
    assert artifact.artifact_type == "code"
    assert artifact.language is None
    assert artifact.related_baseline_id is None


def test_paper_note_defaults():
    note = PaperNote(paper_id="paper_1", method="transformer")
    assert note.datasets == []
    assert note.metrics == []
    assert note.baselines == []
    assert note.important_sections == []
    assert note.limitations is None
