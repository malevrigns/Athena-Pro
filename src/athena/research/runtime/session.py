"""Research session orchestration (roadmap section 7).

`ResearchSession` is the entry point that ties the runtime together: it
hydrates `ResearchRuntimeState`, optionally blocks on a plan-review checkpoint,
then runs the `AgentLoop`. It is the seam a future `/v1/projects/{id}/runs`
endpoint calls — the loop stays a pure unit, the session owns the wiring.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from athena.research.domain import CheckpointType, ResearchProject, ReviewDecision
from athena.research.persistence import ResearchRepository
from athena.research.tools import ToolRouter

from .checkpoints import CheckpointService
from .loop import AgentBrain, AgentLoop, AgentLoopResult, ApprovalHandler, LoopLimits, deny_all_approvals
from .state import ResearchRuntimeState, load_runtime_state


class PlanReviewOutcome(BaseModel):
    checkpoint_id: str
    decision: ReviewDecision
    comment: str | None = None


class SessionResult(BaseModel):
    project_id: str
    started: bool
    plan_review: PlanReviewOutcome | None = None
    loop_result: AgentLoopResult | None = None
    state: ResearchRuntimeState = Field(default_factory=ResearchRuntimeState)


class ResearchSession:
    """Owns one research run: state hydration, plan review, agent loop."""

    def __init__(
        self,
        *,
        repository: ResearchRepository,
        router: ToolRouter,
        project: ResearchProject,
        checkpoints: CheckpointService | None = None,
        limits: LoopLimits | None = None,
        task_id: str | None = None,
    ) -> None:
        self._repository = repository
        self._router = router
        self._project = project
        self._checkpoints = checkpoints or CheckpointService(repository)
        self._limits = limits
        self._task_id = task_id or project.id

    @property
    def checkpoints(self) -> CheckpointService:
        return self._checkpoints

    async def run(
        self,
        *,
        brain: AgentBrain,
        goal: str,
        plan: dict | None = None,
        require_plan_review: bool = False,
        approval_handler: ApprovalHandler = deny_all_approvals,
    ) -> SessionResult:
        """Run the session.

        With `require_plan_review`, a `plan_review` checkpoint is opened and the
        run blocks until it is decided; anything other than `approved` stops the
        run before the agent loop starts.
        """
        state = await load_runtime_state(self._repository, self._project.id)
        if plan is not None:
            state.plan = plan

        plan_review: PlanReviewOutcome | None = None
        if require_plan_review:
            checkpoint = await self._checkpoints.open(
                task_id=self._task_id,
                project_id=self._project.id,
                checkpoint_type=CheckpointType.plan_review,
                title="Approve the research plan",
                content=plan or {},
            )
            decided = await self._checkpoints.wait(checkpoint.id)
            plan_review = PlanReviewOutcome(
                checkpoint_id=checkpoint.id,
                decision=decided.decision or ReviewDecision.pending,
                comment=decided.comment,
            )
            state.review_decisions.append(decided)
            if decided.decision is not ReviewDecision.approved:
                return SessionResult(
                    project_id=self._project.id,
                    started=False,
                    plan_review=plan_review,
                    state=state,
                )

        loop = AgentLoop(
            brain=brain,
            router=self._router,
            limits=self._limits,
            approval_handler=approval_handler,
            repository=self._repository,
            task_id=self._task_id,
            project_id=self._project.id,
        )
        loop_result = await loop.run(goal)
        state.register_loop_result(loop_result)
        return SessionResult(
            project_id=self._project.id,
            started=True,
            plan_review=plan_review,
            loop_result=loop_result,
            state=state,
        )
