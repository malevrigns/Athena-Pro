# Athena Research OS 工程实施计划

本文档承接 `docs/RESEARCH_OS_ROADMAP.md`，用于指导实际开发。Roadmap 说明“要变成什么”，本文说明“怎么改代码”。

## 1. 实施原则

本次改造不是重写项目，而是分层替换。

核心原则：

- 保留现有 FastAPI、Vue、SSE、SQLite、Settings、报告渲染和任务历史。
- 新增 Research OS 领域模型，不把研究资产继续塞进 Markdown。
- 新增 typed event protocol，不继续使用松散 `type: str + payload: dict` 作为长期协议。
- 新增 ToolRouter 和 ToolObservation，所有工具调用必须可追踪。
- 新增真正阻塞的 review checkpoint。
- Agent 编排默认走 LangGraph；旧 async runner 只作为兼容路径保留。
- LangGraph 不直接展开 `ResearchState` 字段，统一通过 graph envelope 持有运行时状态。

## 2. 推荐目录结构

### 2.1 后端新增目录

建议新增：

```text
src/athena/research/
  __init__.py
  domain/
    __init__.py
    models.py
    enums.py
    validators.py
  events/
    __init__.py
    schemas.py
    emitters.py
  runtime/
    __init__.py
    session.py
    loop.py
    context.py
    state.py
    checkpoints.py
  tools/
    __init__.py
    base.py
    router.py
    paper_tools.py
    evidence_tools.py
    taxonomy_tools.py
    baseline_tools.py
    code_tools.py
    experiment_tools.py
  artifacts/
    __init__.py
    models.py
    writer.py
    reader.py
  governance/
    __init__.py
    approval.py
    policy.py
    audit.py
  persistence/
    __init__.py
    repository.py
    sqlite_repository.py
```

现有模块迁移方向：

```text
src/athena/agents/*        -> 逐步变成 role prompt / runtime role
src/athena/graph/main_graph.py -> LangGraph 编排入口，保留 legacy runner 兼容旧流
src/athena/tools/*         -> 可包装成 research/tools/*
src/athena/events.py       -> 保留旧接口，逐步代理到 research/events
src/athena/schemas.py      -> 保留 API schema，逐步拆 domain schema
```

### 2.2 后端 API 新增文件

建议新增：

```text
src/athena/api/projects.py
src/athena/api/research_runs.py
src/athena/api/research_artifacts.py
src/athena/api/research_reviews.py
src/athena/api/research_trace.py
```

短期可以先注册到现有 `api/main.py`，后续再整理 router。

### 2.3 前端新增目录

建议新增：

```text
web/src/types/
  research.ts
  researchEvents.ts
  tools.ts

web/src/stores/
  projects.ts
  researchRun.ts
  researchTrace.ts

web/src/views/projects/
  ProjectListView.vue
  ProjectOverviewView.vue
  ProjectLiteratureView.vue
  ProjectTaxonomyView.vue
  ProjectBaselinesView.vue
  ProjectIdeasView.vue
  ProjectExperimentsView.vue
  ProjectArtifactsView.vue
  ProjectReportView.vue
  ProjectTraceView.vue

web/src/components/research/
  PaperTable.vue
  PaperMatrix.vue
  EvidencePanel.vue
  TaxonomyGraph.vue
  BaselineRankTable.vue
  IdeaRankTable.vue
  ExperimentRunTable.vue
  ArtifactBrowser.vue
  ToolTraceTimeline.vue
  ReviewCheckpointPanel.vue
```

现有页面迁移方向：

```text
HomeView.vue              -> Project creation / quick start
TaskView.vue              -> Research run view
PlanReviewView.vue        -> Review checkpoint view
CitationCheckView.vue     -> Evidence audit view
ReportsView.vue           -> Project report view
KnowledgeView.vue         -> Paper library / source library
WorkbenchView.vue         -> Project overview / agent control surface
```

## 3. Phase 1：领域模型与事件协议

### 3.1 目标

建立 Research OS 的数据地基。旧报告流可以继续跑，但新产物必须开始结构化落库。

### 3.2 后端任务

新增 `src/athena/research/domain/enums.py`：

```python
from enum import StrEnum


class ProjectStatus(StrEnum):
    draft = "draft"
    planning = "planning"
    running = "running"
    waiting_review = "waiting_review"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PaperScreeningStatus(StrEnum):
    candidate = "candidate"
    included = "included"
    excluded = "excluded"
    read = "read"


class ReviewDecision(StrEnum):
    pending = "pending"
    approved = "approved"
    changes_requested = "changes_requested"
    rejected = "rejected"
```

新增 `src/athena/research/domain/models.py`：

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ResearchProject(BaseModel):
    id: str
    title: str
    field: str | None = None
    research_question: str
    constraints: list[str] = Field(default_factory=list)
    target_venue: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class Paper(BaseModel):
    id: str
    project_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    citation_count: int | None = None
    code_url: str | None = None
    relevance_score: float | None = None
    screening_status: str = "candidate"


class Claim(BaseModel):
    id: str
    project_id: str
    paper_id: str | None = None
    text: str
    claim_type: str
    section: str | None = None
    confidence: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "draft"


class Evidence(BaseModel):
    id: str
    claim_id: str
    source_type: str
    source_url: str | None = None
    paper_id: str | None = None
    section: str | None = None
    quote: str | None = None
    normalized_text: str | None = None
    confidence: float | None = None
    verification_status: str = "unchecked"


class BaselineCandidate(BaseModel):
    id: str
    project_id: str
    name: str
    paper_id: str | None = None
    method_summary: str
    code_url: str | None = None
    dataset: str | None = None
    metric: str | None = None
    reported_score: str | None = None
    reproduction_difficulty: str | None = None
    hardware_requirement: str | None = None
    rank_score: float | None = None
    selection_reason: str | None = None
    status: str = "candidate"


class ResearchIdea(BaseModel):
    id: str
    project_id: str
    title: str
    motivation: str
    core_hypothesis: str
    method_sketch: str
    expected_advantage: str | None = None
    novelty_score: float | None = None
    feasibility_score: float | None = None
    risk_score: float | None = None
    overall_score: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "candidate"


class ExperimentSpec(BaseModel):
    id: str
    project_id: str
    idea_id: str | None = None
    baseline_id: str | None = None
    task: str
    dataset: str | None = None
    metrics: list[str] = Field(default_factory=list)
    train_command: str | None = None
    eval_command: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: list[str] = Field(default_factory=list)
    hardware_requirement: str | None = None
```

### 3.3 SQLite 表

先不用复杂 migration framework，可以在 `sqlite_store.py` 的初始化里追加建表逻辑，但建议把 Research OS 表初始化拆到独立函数。

第一批表：

```sql
research_projects
papers
paper_notes
claims
evidence
baseline_candidates
research_ideas
experiment_specs
experiment_runs
code_artifacts
research_events
tool_calls
tool_observations
review_checkpoints
```

建议所有复杂字段先用 JSON text：

```text
authors
constraints
dataset_mentions
metrics
config
expected_outputs
evidence_ids
artifacts
```

### 3.4 Typed Event

新增 `src/athena/research/events/schemas.py`。

事件基类：

```python
from datetime import datetime
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class EventBase(BaseModel):
    task_id: str
    project_id: str | None = None
    seq: int
    timestamp: datetime


class StatusEvent(EventBase):
    type: Literal["status"] = "status"
    payload: dict


class ToolCallEvent(EventBase):
    type: Literal["tool_call"] = "tool_call"
    payload: dict


class ToolObservationEvent(EventBase):
    type: Literal["tool_observation"] = "tool_observation"
    payload: dict


class PaperFoundEvent(EventBase):
    type: Literal["paper_found"] = "paper_found"
    payload: dict


ResearchEvent = Annotated[
    Union[
        StatusEvent,
        ToolCallEvent,
        ToolObservationEvent,
        PaperFoundEvent,
    ],
    Field(discriminator="type"),
]
```

第一步可以只把 payload 细化到关键事件，不必一次写完全部事件。

### 3.5 前端类型

新增 `web/src/types/researchEvents.ts`：

```ts
import { z } from 'zod'

const EventBase = z.object({
  task_id: z.string(),
  project_id: z.string().nullable().optional(),
  seq: z.number(),
  timestamp: z.string(),
})

export const StatusEvent = EventBase.extend({
  type: z.literal('status'),
  payload: z.object({
    status: z.string(),
    message: z.string().optional(),
  }),
})

export const ToolCallEvent = EventBase.extend({
  type: z.literal('tool_call'),
  payload: z.object({
    tool_call_id: z.string(),
    tool_name: z.string(),
    arguments: z.record(z.string(), z.unknown()),
  }),
})

export const ResearchEvent = z.discriminatedUnion('type', [
  StatusEvent,
  ToolCallEvent,
])

export type ResearchEvent = z.infer<typeof ResearchEvent>
```

### 3.6 前端 handler map

替换长 `if/else` 的方向：

```ts
const handlers = {
  status: applyStatus,
  tool_call: applyToolCall,
  tool_observation: applyToolObservation,
  paper_found: applyPaperFound,
  claim_extracted: applyClaimExtracted,
} satisfies Record<ResearchEvent['type'], EventHandler>
```

要求：

- 未知事件必须记录为 error event 或 ignored event。
- handler 内部只处理对应 payload。
- 不再在一个函数里堆所有业务分支。

### 3.7 Phase 1 验收

- `pytest` 通过。
- `npm run build` 通过。
- 后端 ResearchEvent 可以序列化。
- 前端 Zod 可以 parse 后端样例事件。
- `tests/test_frontend_contract.py` 增加 typed event contract。
- `task.ts` 里的事件处理可以迁移到 handler map。

## 4. Phase 2：LangGraph Runtime、ToolRouter 与 Trace

### 4.1 目标

建立基于 LangGraph 的 agent 编排主路径，以及 agent 可调用、可审批、可追踪的工具层。

Runtime 约束：

- `ATHENA_USE_LANGGRAPH=true` 是生产默认值。
- 缺少 LangGraph 时启动生产编排必须失败，不静默降级。
- `ResearchState` 是唯一业务状态对象。
- LangGraph state 只包含 `runtime: ResearchState` envelope。
- agent node 通过 adapter 接入，图定义只负责节点、边和路由。
- legacy runner 保留用于兼容旧测试和故障定位，不能继续承载新能力。

### 4.2 后端模型

新增 `src/athena/research/tools/base.py`：

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[[dict[str, Any]], Awaitable["ToolResult"]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    permission_level: str
    timeout_seconds: int
    cost_level: str
    handler: ToolHandler


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    summary: str
    structured_output: dict[str, Any]
    raw_output_ref: str | None = None
    error: str | None = None
```

新增 `src/athena/research/tools/router.py`：

```python
class ToolRouter:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def specs_for_llm(self) -> list[dict]:
        ...

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        ...
```

### 4.3 ApprovalPolicy

新增 `src/athena/research/governance/policy.py`：

```python
class ApprovalDecision(BaseModel):
    required: bool
    reason: str | None = None
    risk_level: str = "low"


class ApprovalPolicy:
    def check_tool_call(self, tool: ToolSpec, arguments: dict) -> ApprovalDecision:
        ...
```

默认规则：

```text
read_only                 -> no approval
network_read              -> no approval, rate/cost limited
write_artifact            -> no approval, must record artifact
write_repo                -> approval
run_local_command         -> approval
run_expensive_job         -> approval
external_side_effect      -> approval
destructive               -> deny by default
```

### 4.4 Trace 表

`tool_calls`：

```text
id
task_id
project_id
tool_name
arguments_json
permission_level
approval_status
status
created_at
started_at
finished_at
```

`tool_observations`：

```text
id
tool_call_id
status
summary
structured_output_json
raw_output_ref
error
created_at
```

### 4.5 前端 Trace

新增 `ProjectTraceView.vue`，第一版只需要：

- timeline
- tool name
- arguments summary
- status
- observation summary
- error
- approval required badge

### 4.6 Phase 2 验收

- 至少一个 read-only tool 能通过 ToolRouter 执行。
- 工具调用写入 `tool_calls`。
- 工具结果写入 `tool_observations`。
- SSE 发出 `tool_call` 和 `tool_observation`。
- 前端 Trace 页面能展示调用链。

## 5. Phase 3：Plan Review 真阻塞

### 5.1 目标

Plan Review 不再只是 emit event，而是真正暂停 runtime。

### 5.2 ReviewCheckpoint

新增模型：

```python
class ReviewCheckpoint(BaseModel):
    id: str
    task_id: str
    project_id: str
    checkpoint_type: str
    status: str
    title: str
    content: dict
    decision: str | None = None
    comment: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
```

checkpoint 类型：

```text
plan_review
baseline_selection
experiment_execution
citation_audit
```

### 5.3 Runtime 暂停机制

短期可以进程内 `asyncio.Event`：

```text
create checkpoint
emit review_required
await checkpoint.wait()
if approved: continue
if changes_requested: revise plan
if rejected: cancel
```

生产化阶段再持久化 resume token，支持后端重启恢复。

### 5.4 API

新增：

```text
GET  /api/research/reviews/{checkpoint_id}
POST /api/research/reviews/{checkpoint_id}/approve
POST /api/research/reviews/{checkpoint_id}/request-changes
POST /api/research/reviews/{checkpoint_id}/reject
```

### 5.5 前端

`ReviewCheckpointPanel.vue` 需要展示：

- checkpoint 类型
- plan 内容
- risk/cost/time estimate
- approve
- request changes
- reject
- comment box

### 5.6 Phase 3 验收

- 任务到 Plan Review 时状态变成 `waiting_review`。
- 未点击 approve 前不会进入 researcher。
- approve 后任务继续。
- request changes 后任务回到 planner。
- reject 后任务结束为 cancelled。

## 6. Phase 4：文献调研闭环

### 6.1 第一批文献工具

先实现三个工具：

```text
paper_search
paper_read
citation_graph
```

工具输出必须是结构化对象，不只是文本。

`paper_search` 输出：

```text
papers: Paper[]
query
source
total
```

`paper_read` 输出：

```text
paper_id
sections
method_summary
experiment_summary
result_summary
limitations
```

`citation_graph` 输出：

```text
paper_id
references
citations
influential_citations
```

### 6.2 PaperMatrix

第一版 paper matrix 字段：

```text
title
year
venue
problem
method
dataset
metric
reported_score
baselines
code_url
limitations
relevance_score
reproducibility_score
```

输出格式：

- SQLite rows
- JSON artifact
- CSV artifact

### 6.3 Evidence 抽取

每篇 included paper 至少抽：

- method claim
- dataset claim
- result claim
- limitation claim
- implementation claim if code exists

每个 claim 必须关联 evidence。

### 6.4 Phase 4 验收

- 输入研究问题后，能生成论文候选表。
- 用户能看到筛选状态。
- included paper 能生成 paper note。
- paper matrix 能导出 CSV。
- 至少关键 claim 能关联 evidence。

## 7. Phase 5：Baseline 与 Idea

### 7.1 Baseline Ranking

baseline 排名建议使用多维评分：

```text
reported_strength
code_availability
dataset_availability
implementation_complexity
hardware_cost
license_safety
relevance_to_user_goal
```

总分不是简单平均，应保留每项分数和解释。

### 7.2 Idea Ranking

idea 排名建议使用：

```text
novelty
feasibility
expected_gain
evidence_support
risk
experiment_cost
baseline_compatibility
```

每个 idea 必须有：

- motivation
- hypothesis
- method sketch
- required baseline
- required dataset
- expected metric movement
- failure mode
- ablation plan

### 7.3 Review

baseline selection 必须阻塞。

用户确认前：

- 不生成复现代码。
- 不写实验目录。
- 不运行任何命令。

### 7.4 Phase 5 验收

- 能生成 baseline 排名。
- 能解释为什么选择某个 baseline。
- 能生成至少 3 个 idea。
- idea 能按分数排序。
- 用户确认 baseline 后，进入代码阶段。

## 8. Phase 6：代码与实验框架

### 8.1 实验目录生成

生成目录：

```text
experiments/<project_slug>/
  README.md
  papers/
  baselines/
  proposed/
  runs/
```

写文件必须通过 `code_artifact_write` 工具，并记录 `CodeArtifact`。

### 8.2 Baseline 复现文件

每个 baseline 至少生成：

```text
README.md
requirements.txt
config.yaml
train.py
eval.py
reproduce.sh
results.json
```

### 8.3 Proposed Method 文件

每个 proposed method 至少生成：

```text
README.md
requirements.txt
config.yaml
train.py
eval.py
ablation.yaml
run.sh
```

### 8.4 命令执行

任何命令执行前必须：

- 生成 `experiment_execution` checkpoint。
- 展示 command、cwd、env、files touched。
- 用户 approve 后才执行。

### 8.5 Phase 6 验收

- 选定 baseline 后能生成实验目录。
- 所有生成文件都有 artifact record。
- 用户 approve 后可以执行 dry-run 或 test command。
- 运行结果能写入 `ExperimentRun`。
- 前端能展示 stdout/stderr/metrics。

## 9. API 设计

### 9.1 Projects

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

### 9.2 Research Runs

```text
POST   /api/projects/{project_id}/runs
GET    /api/projects/{project_id}/runs
GET    /api/runs/{run_id}
POST   /api/runs/{run_id}/cancel
GET    /api/runs/{run_id}/events
```

### 9.3 Literature

```text
GET    /api/projects/{project_id}/papers
POST   /api/projects/{project_id}/papers
PATCH  /api/projects/{project_id}/papers/{paper_id}
GET    /api/projects/{project_id}/paper-matrix
```

### 9.4 Evidence

```text
GET    /api/projects/{project_id}/claims
GET    /api/projects/{project_id}/evidence
POST   /api/projects/{project_id}/evidence/audit
```

### 9.5 Baselines / Ideas / Experiments

```text
GET    /api/projects/{project_id}/baselines
GET    /api/projects/{project_id}/ideas
GET    /api/projects/{project_id}/experiments
POST   /api/projects/{project_id}/experiments/{experiment_id}/run
```

### 9.6 Trace

```text
GET    /api/runs/{run_id}/trace
GET    /api/runs/{run_id}/tool-calls
GET    /api/runs/{run_id}/tool-observations
```

## 10. 测试计划

### 10.1 后端测试

新增：

```text
tests/research/test_domain_models.py
tests/research/test_event_schemas.py
tests/research/test_tool_router.py
tests/research/test_approval_policy.py
tests/research/test_review_checkpoints.py
tests/research/test_sqlite_repository.py
```

### 10.2 前端测试

如果现有项目暂时没有前端测试框架，至少先做：

- `npm run build`
- TypeScript check
- Zod schema sample parse
- contract fixture check

### 10.3 Contract Test

后端导出 event fixture：

```text
tests/fixtures/research_events/*.json
```

前端 schema 需要能 parse。

后端也要测试：

- 所有 fixture 都能被 Pydantic parse。
- 所有 event type 都有前端 handler。

## 11. 迁移策略

### 11.1 第一阶段兼容旧 task

旧 `/api/tasks` 不要立刻删除。

做法：

- 旧 task 创建时自动创建一个 `ResearchProject` shadow record。
- 旧 event 继续发。
- 新 ResearchEvent 同步写入 `research_events`。
- 前端先保持旧 TaskView 可用。

### 11.2 第二阶段新旧并行

新增 `/projects` 路由。

用户可以选择：

- old task flow
- research project flow

### 11.3 第三阶段默认切换

默认进入 research project flow。

旧 task flow 只作为 legacy compatibility。

### 11.4 第四阶段收敛

`main_graph.py` 变成 wrapper：

```text
legacy task request -> create ResearchProject -> run ResearchRuntime
```

## 12. 风险点

### 12.1 范围过大

风险：一次性改 runtime、模型、前端、工具，容易失控。

控制方式：

- Phase 1 只建模型和事件。
- Phase 2 只接一个工具。
- Phase 3 只做 Plan Review 真阻塞。
- Phase 4 再做文献闭环。

### 12.2 事件协议漂移

风险：后端新增事件，前端忘记处理。

控制方式：

- discriminated union
- contract test
- handler coverage test

### 12.3 工具输出不可控

风险：工具返回大段文本，无法进入结构化资产。

控制方式：

- ToolResult 必须包含 `structured_output`。
- raw text 只能作为 artifact 引用。

### 12.4 人在回路假阻塞

风险：UI 有审核按钮，但后端实际继续跑。

控制方式：

- checkpoint 状态必须写库。
- runtime 必须 await checkpoint。
- 测试覆盖“未 approve 不进入下一阶段”。

### 12.5 实验执行安全

风险：agent 自动运行危险命令。

控制方式：

- local command 默认审批。
- destructive command 默认禁止。
- command/cwd/env/files touched 必须展示。

## 13. 近期最小开发序列

这里的“最小”不是产品 MVP，而是工程依赖顺序。

建议按这个顺序动代码：

1. 新增 `src/athena/research/domain`。
2. 新增 Research OS SQLite 表。
3. 新增 `research_events` typed schema。
4. 前端新增 `researchEvents.ts`。
5. 增加后端/前端 event contract test。
6. 改 `task.ts` 的 `applyEvent` 为 handler map。
7. 将生产编排切到 LangGraph。
8. 新增 LangGraph node adapter / graph state envelope。
9. 新增 `ToolSpec` / `ToolRouter`。
10. 新增 `tool_calls` / `tool_observations` 表。
11. 新增 `paper_search` skeleton tool。
12. 新增 Trace event。
13. 新增 Project routes skeleton。
14. 新增 Project list / overview 页面 skeleton。
15. 实现 Plan Review checkpoint 真阻塞。
16. 把旧 planner 输出写入 ResearchProject plan artifact。
17. 开始接 paper search / paper read。

完成前 17 步后，项目会从“报告 pipeline”正式进入“研究资产 runtime”的形态。
