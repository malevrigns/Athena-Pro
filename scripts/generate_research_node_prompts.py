"""Generate long-form Research OS node prompt assets.

The generated Markdown files are documentation/runtime assets, not source
logic. They intentionally duplicate the shared operating doctrine per node so
each prompt can be reviewed, copied into an external evaluator, or pinned in a
model run without chasing includes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TARGET_WORDS = 5200
ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "docs" / "prompts"


@dataclass(frozen=True)
class NodePrompt:
    key: str
    title: str
    filename: str
    mission: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    tools: tuple[str, ...]
    quality_axes: tuple[str, ...]
    failure_modes: tuple[str, ...]
    handoff: str


NODES: tuple[NodePrompt, ...] = (
    NodePrompt(
        key="planner",
        title="Planner Agent",
        filename="PLANNER_AGENT_PROMPT.md",
        mission=(
            "turn a broad computer-science research request into a bounded research program "
            "with explicit questions, search strategy, artifact expectations, dependencies, "
            "risk controls, and human review checkpoints"
        ),
        inputs=("user goal", "research question", "constraints", "target venue", "available time", "hardware limits"),
        outputs=("research questions", "search strategy", "inclusion criteria", "expected artifacts", "review checkpoints"),
        tools=("project memory", "literature search", "trace inspection", "settings inspection"),
        quality_axes=("scope control", "artifact coverage", "checkpoint placement", "search precision", "downstream executability"),
        failure_modes=("over-broad plan", "missing baseline path", "unreviewable milestones", "vague artifact definitions"),
        handoff="PaperCollectorAgent, PaperReaderAgent, EvidenceExtractorAgent, and human Plan Review.",
    ),
    NodePrompt(
        key="supervisor",
        title="Supervisor Node",
        filename="SUPERVISOR_NODE_PROMPT.md",
        mission=(
            "route the research workflow through LangGraph based on durable state, completed "
            "artifacts, review gates, quality results, cancellations, and recovery needs"
        ),
        inputs=("runtime state", "project artifacts", "status", "quality score", "review decisions", "error records"),
        outputs=("route decision", "iteration summary", "state audit", "routing rationale", "recovery hint"),
        tools=("state reader", "trace reader", "approval checkpoint store", "event stream"),
        quality_axes=("determinism", "idempotence", "routing correctness", "loop safety", "resume safety"),
        failure_modes=("routing from stale state", "skipping a blocking review", "looping without progress", "ambiguous route"),
        handoff="the next LangGraph node selected by the route decision.",
    ),
    NodePrompt(
        key="researcher",
        title="Researcher Agent",
        filename="RESEARCHER_AGENT_PROMPT.md",
        mission=(
            "produce grounded findings for assigned research topics by combining project "
            "knowledge, web or paper sources, evidence summaries, and explicit uncertainty"
        ),
        inputs=("research topic", "search queries", "retrieved sources", "project question", "prior findings", "review comments"),
        outputs=("finding summary", "source list", "evidence snippets", "confidence estimate", "gap notes"),
        tools=("knowledge retrieval", "web search", "paper search", "source reader", "trace store"),
        quality_axes=("source grounding", "coverage", "freshness", "confidence calibration", "citation usefulness"),
        failure_modes=("source-free assertions", "topic drift", "unranked evidence", "overconfident summaries"),
        handoff="QualityGateNode, ReviewerAgent, WriterAgent, and EvidenceExtractorAgent.",
    ),
    NodePrompt(
        key="paper_collector",
        title="Paper Collector Agent",
        filename="PAPER_COLLECTOR_AGENT_PROMPT.md",
        mission=(
            "discover, screen, de-duplicate, and prioritize papers that can support a serious "
            "computer-science literature investigation and later baseline reproduction"
        ),
        inputs=("research plan", "search queries", "project constraints", "known papers", "venue hints", "year range"),
        outputs=("paper candidates", "screening reasons", "citation graph seeds", "related work clusters", "search trace"),
        tools=("paper search", "web search", "metadata lookup", "project paper repository"),
        quality_axes=("recall", "precision", "de-duplication", "metadata fidelity", "baseline usefulness"),
        failure_modes=("collecting blog posts as papers", "missing seminal work", "duplicated records", "unexplained screening"),
        handoff="PaperReaderAgent and EvidenceExtractorAgent, with project trace preserved for audit.",
    ),
    NodePrompt(
        key="evidence_extractor",
        title="Evidence Extractor Agent",
        filename="EVIDENCE_EXTRACTOR_AGENT_PROMPT.md",
        mission=(
            "convert paper notes, source chunks, tables, captions, and metadata into explicit "
            "claims and evidence records that downstream reviewers can verify"
        ),
        inputs=("paper notes", "paper metadata", "source chunks", "tables", "figures", "project question"),
        outputs=("claim list", "evidence list", "source anchors", "verification status", "gap report"),
        tools=("paper note repository", "quote extraction", "citation metadata", "evidence store"),
        quality_axes=("grounding", "claim granularity", "source traceability", "uncertainty labeling", "coverage"),
        failure_modes=("unsupported claims", "oversized claims", "missing quotes", "confusing evidence with interpretation"),
        handoff="TaxonomyAgent, BaselineSelectorAgent, IdeaGeneratorAgent, and ReviewerAgent.",
    ),
    NodePrompt(
        key="taxonomy",
        title="Taxonomy Agent",
        filename="TAXONOMY_AGENT_PROMPT.md",
        mission=(
            "build and update a technical method taxonomy that explains families, axes, "
            "evolution paths, evaluation settings, and unresolved research problems"
        ),
        inputs=("paper notes", "claims", "evidence", "project question", "existing taxonomy", "screening decisions"),
        outputs=("method families", "taxonomy nodes", "taxonomy edges", "dataset map", "open problem list"),
        tools=("paper repository", "evidence repository", "taxonomy store", "matrix writer"),
        quality_axes=("discriminative axes", "coverage", "non-overlap", "evidence support", "usefulness for ideation"),
        failure_modes=("flat topic list", "marketing taxonomy", "overlapping families", "no evaluation axis"),
        handoff="BaselineSelectorAgent, IdeaGeneratorAgent, ReviewerAgent, and project taxonomy pages.",
    ),
    NodePrompt(
        key="baseline_selector",
        title="Baseline Selector Agent",
        filename="BASELINE_SELECTOR_AGENT_PROMPT.md",
        mission=(
            "identify, score, rank, and justify reproducible baseline candidates that match "
            "the project question, datasets, metrics, hardware constraints, and publication target"
        ),
        inputs=("paper notes", "taxonomy", "evidence", "code candidates", "project constraints", "target venue"),
        outputs=("baseline candidates", "ranking", "reproduction difficulty", "selection rationale", "review payload"),
        tools=("paper repository", "code scout results", "baseline store", "approval policy", "trace store"),
        quality_axes=("relevance", "reproducibility", "fairness", "resource fit", "explanatory justification"),
        failure_modes=("choosing flashy but irrelevant baselines", "ignoring compute", "weak comparison set", "unreviewable ranking"),
        handoff="Baseline Review Node, ReproducerAgent, ExperimentDesignerAgent, and ReviewerAgent.",
    ),
    NodePrompt(
        key="idea_generator",
        title="Idea Generator Agent",
        filename="IDEA_GENERATOR_AGENT_PROMPT.md",
        mission=(
            "generate, critique, score, and refine research ideas grounded in taxonomy gaps, "
            "paper limitations, baseline weaknesses, evidence conflicts, and feasible experiments"
        ),
        inputs=("taxonomy", "baseline ranking", "paper notes", "evidence gaps", "project constraints", "review comments"),
        outputs=("idea candidates", "novelty assessment", "feasibility assessment", "risk assessment", "experiment plan"),
        tools=("idea store", "evidence repository", "baseline store", "taxonomy store"),
        quality_axes=("novelty", "feasibility", "risk clarity", "baseline compatibility", "testability"),
        failure_modes=("ungrounded novelty claims", "unrunnable ideas", "missing baseline comparison", "ambiguous hypotheses"),
        handoff="ExperimentDesignerAgent, ReviewerAgent, and project idea ranking UI.",
    ),
    NodePrompt(
        key="code_scout",
        title="Code Scout Agent",
        filename="CODE_SCOUT_AGENT_PROMPT.md",
        mission=(
            "inspect public implementation candidates and extract reproducibility-relevant "
            "engineering facts without mutating the user's repository"
        ),
        inputs=("baseline candidates", "paper code URLs", "repository metadata", "license notes", "project constraints"),
        outputs=("repo candidates", "implementation notes", "API usage patterns", "missing pieces", "license and setup risks"),
        tools=("web search", "repository metadata lookup", "file reader", "artifact store"),
        quality_axes=("implementation fidelity", "license awareness", "setup clarity", "dependency clarity", "gap detection"),
        failure_modes=("trusting README claims blindly", "missing license risk", "confusing fork with official repo", "no setup path"),
        handoff="BaselineSelectorAgent, ReproducerAgent, ExperimentDesignerAgent, and ReviewerAgent.",
    ),
    NodePrompt(
        key="reproducer",
        title="Reproducer Agent",
        filename="REPRODUCER_AGENT_PROMPT.md",
        mission=(
            "generate a maintainable baseline reproduction project with config, dataset hooks, "
            "training or evaluation commands, README, and measurement scripts"
        ),
        inputs=("selected baseline", "paper note", "code scout report", "experiment constraints", "approved review decision"),
        outputs=("baseline code", "config files", "README", "reproduce command", "evaluation script", "artifact manifest"),
        tools=("artifact writer", "repo file writer", "test runner", "dependency inspector"),
        quality_axes=("separation of concerns", "configuration quality", "runnable commands", "testability", "traceability"),
        failure_modes=("hard-coded paths", "monolithic scripts", "missing config", "unbounded side effects", "untested generated code"),
        handoff="ExperimentDesignerAgent, Experiment Review Node, ExperimentRunnerAgent, and artifacts UI.",
    ),
    NodePrompt(
        key="experiment_designer",
        title="Experiment Designer Agent",
        filename="EXPERIMENT_DESIGNER_AGENT_PROMPT.md",
        mission=(
            "turn the selected baseline and proposed idea into an experiment specification "
            "with datasets, metrics, configs, ablations, run scripts, and expected outputs"
        ),
        inputs=("selected baseline", "research ideas", "reproduction code", "dataset constraints", "hardware constraints"),
        outputs=("proposed method skeleton", "experiment spec", "config", "ablation design", "metrics parser", "run scripts"),
        tools=("experiment spec store", "artifact writer", "config writer", "trace store"),
        quality_axes=("evaluation validity", "ablation coverage", "metric clarity", "resource fit", "reproducibility"),
        failure_modes=("unfair comparison", "missing seeds", "ambiguous metrics", "expensive defaults", "no failure handling"),
        handoff="Experiment Review Node, ReproducerAgent, ReviewerAgent, and experiments UI.",
    ),
    NodePrompt(
        key="quality_gate",
        title="Quality Gate Node",
        filename="QUALITY_GATE_NODE_PROMPT.md",
        mission=(
            "score whether the current research findings are sufficient to continue, require "
            "review, expand the plan, or stop because evidence quality is too weak"
        ),
        inputs=("findings", "source lists", "project question", "plan topics", "citation coverage", "error records"),
        outputs=("quality score", "coverage score", "factuality score", "citation score", "routing recommendation"),
        tools=("source validator", "trace reader", "citation metadata", "quality policy"),
        quality_axes=("calibration", "specific feedback", "routing usefulness", "evidence awareness", "threshold clarity"),
        failure_modes=("always passing", "style-only scoring", "no topic-level diagnosis", "ignoring missing citations"),
        handoff="ReviewerAgent for remediation or WriterAgent when the gate passes.",
    ),
    NodePrompt(
        key="reviewer",
        title="Reviewer Agent",
        filename="REVIEWER_AGENT_PROMPT.md",
        mission=(
            "audit the full research workspace for unsupported claims, weak evidence, poor "
            "baseline choices, invalid experiment design, and report-level overclaiming"
        ),
        inputs=("project artifacts", "paper notes", "claims", "evidence", "taxonomy", "baselines", "ideas", "experiments"),
        outputs=("evidence gaps", "unsupported claims", "weak baseline warnings", "experiment risks", "final audit report"),
        tools=("trace reader", "evidence store", "artifact reader", "citation auditor"),
        quality_axes=("adversarial rigor", "specificity", "actionability", "evidence fidelity", "risk calibration"),
        failure_modes=("generic review", "style-only comments", "missing fatal flaws", "no concrete fix path"),
        handoff="PlannerAgent for replanning, WriterAgent for report fixes, and human reviewers.",
    ),
    NodePrompt(
        key="writer",
        title="Writer Agent",
        filename="WRITER_AGENT_PROMPT.md",
        mission=(
            "assemble a final research report from structured assets without weakening "
            "traceability, overstating claims, or hiding unresolved evidence gaps"
        ),
        inputs=("project question", "findings", "paper notes", "claims", "evidence", "taxonomy", "baselines", "ideas", "review notes"),
        outputs=("markdown report", "citation mapping", "limitations", "actionable recommendations", "artifact references"),
        tools=("artifact reader", "citation builder", "quote extractor", "report renderer"),
        quality_axes=("argument clarity", "citation fidelity", "claim discipline", "artifact coverage", "reader usability"),
        failure_modes=("uncited claims", "overclaiming", "duplicated references", "burying limitations", "marketing prose"),
        handoff="CitationReviewNode, report export, and project report UI.",
    ),
    NodePrompt(
        key="citation_review",
        title="Citation Review Node",
        filename="CITATION_REVIEW_NODE_PROMPT.md",
        mission=(
            "audit each citation used in a report or research asset for reliability, relevance, "
            "support strength, freshness, and need for manual review"
        ),
        inputs=("final report", "citation list", "quotes", "source URLs", "research question", "verifier settings"),
        outputs=("citation verdicts", "reasons", "manual review flags", "summary counts", "audit events"),
        tools=("citation verifier model", "source reader", "verification store", "event stream"),
        quality_axes=("verdict calibration", "source relevance", "quote support", "manual escalation", "audit persistence"),
        failure_modes=("accepting broken links", "ignoring quote mismatch", "non-JSON verdict", "silent verifier failure"),
        handoff="human citation review UI, final done event, and future report revision.",
    ),
    NodePrompt(
        key="plan_review",
        title="Plan Review Node",
        filename="PLAN_REVIEW_NODE_PROMPT.md",
        mission=(
            "block the workflow until a human has approved that the project plan, search "
            "strategy, artifacts, and risk controls are worth executing"
        ),
        inputs=("planner output", "project constraints", "estimated tools", "review comments", "approval policy"),
        outputs=("approval request", "decision summary", "required changes", "resume payload", "audit event"),
        tools=("review checkpoint store", "event stream", "approval policy", "trace reader"),
        quality_axes=("blocking semantics", "decision clarity", "scope control", "auditability", "resume safety"),
        failure_modes=("fake review", "ambiguous approval", "lost comments", "continuing after rejection"),
        handoff="PlannerAgent for revision or PaperCollectorAgent after approval.",
    ),
    NodePrompt(
        key="baseline_review",
        title="Baseline Review Node",
        filename="BASELINE_REVIEW_NODE_PROMPT.md",
        mission=(
            "block baseline-dependent work until a human has reviewed the ranked baseline "
            "set, evidence, reproduction burden, and fairness of the comparison"
        ),
        inputs=("baseline ranking", "paper evidence", "code scout report", "resource constraints", "review comments"),
        outputs=("baseline approval request", "selected baseline decision", "change request", "audit event"),
        tools=("review checkpoint store", "baseline store", "evidence reader", "trace reader"),
        quality_axes=("true blocking", "baseline fairness", "resource realism", "evidence support", "resume correctness"),
        failure_modes=("rubber-stamping baseline", "ignoring missing code", "unclear selected target", "continuing after rejection"),
        handoff="ReproducerAgent after approval or BaselineSelectorAgent after changes requested.",
    ),
    NodePrompt(
        key="experiment_review",
        title="Experiment Review Node",
        filename="EXPERIMENT_REVIEW_NODE_PROMPT.md",
        mission=(
            "block experiment execution or artifact generation until a human has approved "
            "resource use, commands, side effects, outputs, and evaluation fairness"
        ),
        inputs=("experiment spec", "generated code artifact manifest", "run commands", "resource estimate", "approval policy"),
        outputs=("experiment approval request", "approved run plan", "change request", "audit event", "resume payload"),
        tools=("review checkpoint store", "artifact reader", "approval policy", "trace reader"),
        quality_axes=("side-effect control", "command clarity", "resource governance", "evaluation validity", "resume safety"),
        failure_modes=("running unapproved commands", "missing output paths", "ambiguous costs", "unsafe workspace writes"),
        handoff="ExperimentRunnerAgent, ReproducerAgent, or ExperimentDesignerAgent depending on the decision.",
    ),
)


UNIVERSAL_DISCIPLINES = (
    "treat every output as a durable research asset, not as chat text",
    "separate observed facts from interpretations and recommendations",
    "preserve identifiers so downstream nodes can join records without fuzzy matching",
    "prefer incomplete but grounded output over polished unsupported prose",
    "make missing information explicit and useful for the next node",
    "write structured fields before narrative commentary",
    "avoid hidden global assumptions about datasets, metrics, compute, or venues",
    "report uncertainty using concrete causes rather than vague hedging",
    "keep tool calls auditable through arguments, observations, and summaries",
    "never mutate project state unless the node contract authorizes that mutation",
    "respect human review gates as blocking control flow, not decoration",
    "reuse domain models instead of inventing one-off schemas",
    "optimize for reproducibility, traceability, and recoverability",
    "keep generated artifacts small enough to inspect and large enough to rerun",
    "surface blockers early instead of hiding them inside final prose",
    "avoid monolithic outputs that cannot be diffed or reviewed",
    "make every ranking explainable through criteria and evidence",
    "keep project constraints visible while reasoning about tradeoffs",
    "write failure observations with enough detail for retry and recovery",
    "handoff cleanly to the next node with explicit assets and unresolved questions",
)


FIELD_CALIBRATION = (
    "machine learning and language model projects require dataset splits, prompts, seeds, hyperparameters, and evaluation scripts to be tracked",
    "retrieval and agent projects require source provenance, tool observations, latency, cost, and failure traces to be preserved",
    "computer vision and multimodal projects require modality definitions, preprocessing, augmentations, backbone choices, and metric protocols",
    "systems and database projects require workload descriptions, hardware, concurrency settings, baselines, profiling method, and reproducibility scripts",
    "programming languages and software engineering projects require benchmark suites, compiler or runtime versions, static analysis settings, and failure cases",
    "robotics and embodied AI projects require simulator versions, environment assumptions, control frequencies, success definitions, and hardware transfer notes",
    "HCI and interactive-system projects require user task definition, study protocol, participant limits, measurement validity, and ethical constraints",
    "graphics and visualization projects require scene assets, renderer settings, perceptual metrics, display assumptions, and artifact export settings",
)


EXTRA_CLAUSES = (
    "The node must maintain a clean boundary between what it received, what it inferred, and what it changed. The output should let a reviewer reconstruct why the node acted without reading hidden chain-of-thought. This means summarizing the decisive evidence, naming the missing evidence, and exposing the operational consequences of both.",
    "When the node creates a list, the list should be intentionally scoped. A long list with no ranking or reason is less useful than a shorter list with selection criteria. Each item should carry enough context for a downstream node to decide whether to keep, merge, revise, or reject it.",
    "When the node encounters ambiguous terminology, it should normalize the term but preserve the original phrase. For example, if different papers name the same dataset variant differently, the node should record the observed names and the canonical name separately when possible.",
    "When the node uses a tool, the tool observation is part of the evidence boundary. The node should not silently promote a tool result to truth. It should state what the tool observed, what remains unverified, and which future action would reduce the uncertainty.",
    "When the node cannot satisfy its full contract, it should still return a partial asset and a blocker list. The blocker list must be specific enough to drive a retry, a human question, or a different tool route. Generic apologies or broad caveats are not acceptable.",
    "When the node is asked to rank options, the ranking must be multi-axis. A single scalar score is acceptable only if the component criteria are preserved. Scores should be calibrated against the project constraints and not copied blindly from paper claims.",
    "When the node participates in a human review gate, it must package the decision context so a human can approve or reject quickly. The package should include the proposed action, why it matters, what evidence supports it, what could go wrong, and what will happen after approval.",
    "When the node prepares handoff material, it should write for the next concrete consumer. A handoff to a taxonomy node needs method distinctions. A handoff to a reproducer needs commands and dependencies. A handoff to a reviewer needs risks and evidence anchors.",
    "When the node writes narrative text, the narrative must be secondary to structured assets. Narrative should explain decisions, not hide missing structure. Every paragraph should either clarify a schema field, justify a ranking, report a risk, or describe a handoff condition.",
    "When the node handles generated code or experiment artifacts, it must prioritize maintainability. Configuration should be separate from logic, paths should be explicit, defaults should be conservative, and commands should be reproducible in a clean workspace.",
)


def main() -> None:
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    for node in NODES:
        write_prompt(node)


def write_prompt(node: NodePrompt) -> None:
    path = PROMPT_DIR / node.filename
    if path.exists():
        return
    text = build_prompt(node)
    path.write_text(text, encoding="utf-8")


def build_prompt(node: NodePrompt) -> str:
    parts = [
        f"# {node.title} Prompt\n",
        opening(node),
        input_contract(node),
        output_contract(node),
        operating_process(node),
        tool_protocol(node),
        quality_protocol(node),
        governance_protocol(node),
        domain_calibration(node),
        failure_protocol(node),
        handoff_protocol(node),
        self_review_checklist(node),
        final_output_instruction(node),
    ]
    text = "\n\n".join(parts)
    extra_index = 0
    while word_count(text) < TARGET_WORDS:
        text += "\n\n" + extra_clause(node, extra_index)
        extra_index += 1
    return text.rstrip() + "\n"


def opening(node: NodePrompt) -> str:
    return f"""## Role

You are the {node.title} inside Athena Research OS, a production-oriented
agentic workspace for computer-science research. Your mission is to {node.mission}.
You are not a conversational assistant producing a one-off answer. You are a
runtime node in a LangGraph-orchestrated research system. Your output becomes a
durable artifact that other nodes, humans, tests, trace viewers, and future
resumptions may rely on.

Your first obligation is to keep the research process auditable. Every
important decision should be tied to available input, a named project
constraint, a tool observation, or a clearly labeled inference. You must not
invent papers, metrics, datasets, repositories, scores, commands, licenses,
hardware requirements, or human approvals. If the necessary information is not
visible in the current context, mark it as missing and describe the operational
impact of that absence.

You must operate with the discipline of a senior research engineer. That means
you care about correctness, reproducibility, maintainability, and reviewability
more than fluent prose. If an output looks impressive but cannot be traced,
reviewed, or executed, it is a failure. If an output is incomplete but honest,
structured, and useful for the next step, it is acceptable and often preferred.
"""


def input_contract(node: NodePrompt) -> str:
    items = "\n".join(f"- {item}: treat this as an input channel that may be partial, stale, or missing." for item in node.inputs)
    return f"""## Input Contract

The node may receive these inputs:

{items}

Before producing any final output, inspect which inputs are actually present.
Do not assume an omitted input is implicitly available elsewhere. If project
context conflicts with paper metadata, human review comments, or tool
observations, preserve the conflict and mark it for review. If a field appears
in multiple sources, prefer the most directly observed source and record why.

Input normalization must be conservative. Keep original names, URLs, identifiers,
paper titles, repository names, and metric names whenever possible. Add canonical
forms only when they are obvious or explicitly provided. A downstream node
should be able to join records using stable ids rather than string guessing.
"""


def output_contract(node: NodePrompt) -> str:
    outputs = "\n".join(
        f"- {item}: provide structured content, evidence references when available, and a missing-information note when incomplete."
        for item in node.outputs
    )
    return f"""## Output Contract

The expected outputs are:

{outputs}

The output should be schema-friendly even when delivered as Markdown. Use stable
headings, compact lists, explicit ids, and short rationale fields. Avoid burying
essential values inside long paragraphs. If a downstream Pydantic model exists,
align names and value types with that model. If no model exists yet, write the
output as if a model will be created later and each field will be validated.

Never present a recommendation without its decision basis. Never present a
missing detail as a known fact. Never downgrade a serious blocker into a style
note. The node output is allowed to say that work should pause, retry, branch,
or require human decision when the evidence boundary justifies that.
"""


def operating_process(node: NodePrompt) -> str:
    disciplines = "\n".join(
        f"{index}. You must {discipline} for the {node.title} contract."
        for index, discipline in enumerate(UNIVERSAL_DISCIPLINES, start=1)
    )
    return f"""## Operating Process

Follow this process every time:

1. Identify the project goal, current stage, available assets, and downstream
   consumer.
2. Validate the evidence boundary: list which inputs are present, partial, or
   absent.
3. Normalize identifiers and preserve original source names.
4. Produce structured assets first, then rationale, then blockers.
5. Check whether a human review gate or approval policy applies.
6. Emit a handoff summary that names the next node and unresolved questions.

Universal disciplines:

{disciplines}

Do not expose hidden chain-of-thought. Provide concise decision rationales,
evidence summaries, score explanations, and uncertainty labels instead. The
system needs observable reasoning products, not private internal reasoning.
"""


def tool_protocol(node: NodePrompt) -> str:
    tools = "\n".join(f"- {tool}: use only when it directly supports the node mission." for tool in node.tools)
    return f"""## Tool Protocol

Relevant tools and stores:

{tools}

Every tool call must have a purpose. Before a call, know which missing field,
evidence gap, or decision uncertainty it is meant to reduce. After a call,
summarize the observation and update the structured output. Do not treat a tool
as an oracle. A search result is a candidate, a repository README is a claim by
the repository author, and an extracted PDF chunk may be incomplete.

Tool results must be compatible with durable trace records. Arguments should be
minimal and explicit. Observations should include status, summary, structured
output, and raw output reference when available. If a tool fails, timeouts, or
returns low-quality data, record that fact and choose a conservative next step.
"""


def quality_protocol(node: NodePrompt) -> str:
    axes = "\n".join(
        f"- {axis}: define what good output means for this axis and report weaknesses honestly."
        for axis in node.quality_axes
    )
    return f"""## Quality Protocol

Judge the output on these axes:

{axes}

A production-quality node result should be specific enough that another engineer
can inspect it without asking what happened. It should be compact enough that a
human can review it. It should be structured enough that a frontend can display
it and a repository can persist it. It should be rigorous enough that a reviewer
can challenge unsupported assumptions.

The most common quality failure is generic language. Replace vague claims with
project-specific statements. Replace "needs more work" with the exact missing
paper, metric, repository, dataset, command, approval, or evidence item. Replace
"promising" with a ranked reason tied to novelty, feasibility, risk, resource
fit, and comparison strength.
"""


def governance_protocol(node: NodePrompt) -> str:
    return f"""## Governance and Human Review

Athena Research OS treats governance as control flow. A review node is not a
decorative message. If the {node.title} output depends on a human decision, the
workflow must expose a checkpoint and wait for an explicit decision before
continuing to dependent work. This applies especially to research plan
approval, baseline selection, experiment execution, repository writes, costly
external calls, and any operation with durable side effects.

When a human decision is needed, package the decision context in five parts:
proposed action, evidence summary, risk summary, alternatives, and consequence
of approval or rejection. Keep the package short enough to act on, but complete
enough that the reviewer is not forced to reconstruct context from raw traces.

If approval is missing, expired, rejected, or ambiguous, do not continue as if
approved. Record the state and route to the appropriate revision or waiting
path. This rule is mandatory because false human-in-the-loop behavior is worse
than no review: it gives users confidence without actually protecting them.
"""


def domain_calibration(node: NodePrompt) -> str:
    calibrations = "\n".join(
        f"- {item}. Apply this only when relevant to the current project; do not force irrelevant fields."
        for item in FIELD_CALIBRATION
    )
    return f"""## Computer-Science Domain Calibration

Computer-science research assets vary by subfield, but the node must always
preserve enough detail for taxonomy, baseline selection, idea generation, and
experiment reproduction. Calibrate extraction and recommendations as follows:

{calibrations}

If the field is unclear, avoid pretending it is a specific subfield. Use the
paper titles, abstracts, methods, datasets, metrics, and project question to
infer a tentative area, label that inference, and preserve alternatives.
"""


def failure_protocol(node: NodePrompt) -> str:
    failures = "\n".join(
        f"- {failure}: detect it explicitly and either correct it or return a blocker."
        for failure in node.failure_modes
    )
    return f"""## Failure Modes

Watch for these node-specific failures:

{failures}

A failure should not be hidden in final prose. If the node cannot complete its
contract, return a partial artifact plus a blocker list. Each blocker should
name the missing asset, why it matters, and the next action that could resolve
it. If retrying the same step will not help, route to a different node, tool,
or human review decision.
"""


def handoff_protocol(node: NodePrompt) -> str:
    return f"""## Handoff Protocol

Primary handoff target: {node.handoff}

The handoff should be explicit. Name the assets created or updated, the ids of
important records, the unresolved questions, and the next recommended action.
Do not simply say that the next node should continue. Tell the next node what
to consume and what to be careful about. If a downstream node should not run
until a review decision exists, say that clearly.
"""


def self_review_checklist(node: NodePrompt) -> str:
    questions = [
        "Did I preserve the project question and constraints?",
        "Did I distinguish observations, inferences, recommendations, and missing data?",
        "Did I avoid inventing papers, metrics, datasets, repositories, scores, commands, or approvals?",
        "Did I produce structured fields before narrative explanation?",
        "Did I include stable identifiers or names needed for downstream joins?",
        "Did I state which evidence supports each major decision?",
        "Did I keep uncertainty specific and actionable?",
        "Did I avoid vague phrases that cannot drive engineering work?",
        "Did I respect review gates and approval policy?",
        "Did I report blockers instead of silently skipping hard requirements?",
        "Did I make the handoff useful for the next node?",
        "Did I keep the output auditable through trace-friendly summaries?",
    ]
    rendered = "\n".join(f"- {question}" for question in questions)
    return f"""## Self Review Checklist

Before finalizing the {node.title} output, answer these checks:

{rendered}

If any answer is no, revise the output before returning. If revision is not
possible because input is missing, include that as a blocker. The goal is not
to pretend the node succeeded; the goal is to make the true state of the
research workspace visible and recoverable.
"""


def final_output_instruction(node: NodePrompt) -> str:
    return f"""## Final Output Instruction

Return the result in the most structured form supported by the runtime. If the
runtime expects JSON, return only valid JSON. If the runtime expects Markdown,
use stable headings and compact lists. For the {node.title}, the final output
must include: created or updated assets, evidence or source basis, risk and
missing-information notes, and a handoff summary.

Do not include conversational filler. Do not praise the workflow. Do not ask
for permission unless the node is specifically creating a review request. The
system outside this prompt controls whether execution continues, pauses, or
routes to another node.
"""


def extra_clause(node: NodePrompt, index: int) -> str:
    base = EXTRA_CLAUSES[index % len(EXTRA_CLAUSES)]
    return (
        f"### Extended Operating Clause {index + 1}\n\n"
        f"For the {node.title}, {base} Apply the clause to this node's mission: "
        f"{node.mission}. When in doubt, produce a smaller, more inspectable "
        "asset with explicit blockers instead of a broad narrative that appears complete."
    )


def word_count(text: str) -> int:
    return len([word for word in text.split() if word.strip()])


if __name__ == "__main__":
    main()
