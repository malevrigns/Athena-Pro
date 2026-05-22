# Athena Research OS 改造规划

> 目标：把 Athena 从“多 Agent 包装的自动报告生成器”改造成面向计算机科研的生产级 Agentic Research Workspace。

## 1. 定位

Athena 的新定位不是“帮用户生成一篇报告”，而是：

**围绕一个计算机科研问题，自动完成文献调研、技术谱系构建、baseline 选择、idea 生成、baseline 复现代码生成，以及 proposed method 实验框架搭建的研究工作台。**

系统最终产物不再只有 Markdown 报告，而是一组可追踪、可审查、可复现的研究资产：

- 论文库
- 论文阅读笔记
- 论文对比矩阵
- 技术谱系
- baseline 候选与排名
- idea 候选与排名
- evidence graph
- baseline 复现代码
- proposed method 实验框架
- 实验配置、日志、指标和 artifact
- 最终研究报告

## 2. 当前问题判断

现有 Athena 的主要问题不是页面不够多，而是底层范式偏弱：

- 当前流程更接近固定 pipeline，而不是真正的 agent loop。
- 后端事件协议过松，`type: str` 和 `payload: dict` 容易造成前后端漂移。
- 前端事件处理依赖长 `if/else`，可维护性会随着事件类型增加迅速下降。
- Plan Review 和 Citation Review 的人在回路语义不够真实，容易变成“看起来有审核，实际上不阻塞”。
- 文献、claim、evidence、baseline、idea、experiment 没有成为一等数据模型。
- 工具调用没有形成统一协议、权限模型和 observation 记录。
- 最终输出偏报告，不偏研究资产和实验资产。
- Citation 检查更多是事后校验，不是贯穿整个研究流程的 evidence 层。

一句话：当前系统可以生成报告，但还不能稳定支撑严肃科研过程。

## 3. 战略选择

不要推倒重来。应保留 Athena 的产品壳，替换研究内核。

### 保留

- FastAPI 后端
- Vue 前端
- SSE 事件流
- Task 历史
- Settings
- Knowledge/Citation 相关页面
- Markdown 报告导出
- 成本统计
- SQLite 初期存储

### 重写或重构

- 固定的 graph pipeline
- 松散的 `StreamEvent`
- 假阻塞的 Plan Review / Citation Review
- 报告导向的 agent 输出
- 缺少统一协议的工具调用
- 缺少 observation 和 trace 的执行模型

## 4. 目标架构

新 Athena 应拆成六层：

```text
Frontend Research Workspace
        |
Typed Event Stream
        |
Agent Runtime Layer
        |
Tool Router / Approval Policy
        |
Research Domain Layer
        |
Artifact & Persistence Layer
```

### 4.1 Research Domain Layer

负责定义研究资产。

核心对象：

- `ResearchProject`
- `Paper`
- `PaperNote`
- `PaperMatrix`
- `Claim`
- `Evidence`
- `MethodTaxonomy`
- `BaselineCandidate`
- `ResearchIdea`
- `ExperimentSpec`
- `ExperimentRun`
- `CodeArtifact`

### 4.2 Agent Runtime Layer

负责执行 agent loop，而不是固定 pipeline。生产编排必须基于 LangGraph；普通
async runner 只能作为兼容和测试路径，不能作为后续能力扩展的主路径。

核心能力：

- session 管理
- LangGraph 状态图编排
- 上下文管理
- tool call 解析
- tool observation 写入
- agent event 发送
- approval pause/resume
- context compaction
- loop guard
- retry / error recovery

### 4.3 Tool Layer

负责把外部世界变成结构化 observation。

核心能力：

- 论文搜索
- 论文读取
- citation graph
- claim 抽取
- GitHub 代码搜索
- repo 文件读取
- dataset 检查
- experiment spec 生成
- 代码 artifact 写入
- 测试命令运行

### 4.4 Artifact Layer

负责保存所有中间产物和最终产物。

核心能力：

- JSON artifact
- Markdown artifact
- CSV matrix
- experiment config
- generated code
- logs
- metrics
- report export

### 4.5 Review / Governance Layer

负责人在回路和权限治理。

核心能力：

- Plan Review 阻塞
- Baseline Selection Review 阻塞
- Experiment Execution Review 阻塞
- destructive tool approval
- external API cost guard
- citation audit
- evidence completeness check

### 4.6 Frontend Workspace Layer

负责把 agent 过程展示成可操作的研究工作台。

核心页面：

```text
/projects
/projects/:id/overview
/projects/:id/literature
/projects/:id/taxonomy
/projects/:id/baselines
/projects/:id/ideas
/projects/:id/experiments
/projects/:id/artifacts
/projects/:id/report
/projects/:id/trace
```

## 5. 核心数据模型

### 5.1 ResearchProject

代表一个研究任务。

字段建议：

```text
id
title
field
research_question
constraints
target_venue
created_at
updated_at
status
owner
```

### 5.2 Paper

代表一篇论文。

字段建议：

```text
id
project_id
title
authors
year
venue
abstract
url
pdf_url
arxiv_id
doi
semantic_scholar_id
citation_count
code_url
dataset_mentions
screening_status
relevance_score
```

### 5.3 PaperNote

代表对论文的结构化阅读。

字段建议：

```text
id
paper_id
problem
method
training_setup
datasets
metrics
baselines
main_results
limitations
reproducibility_notes
important_sections
```

### 5.4 Claim

代表一个可验证结论。

字段建议：

```text
id
project_id
paper_id
text
claim_type
section
confidence
evidence_ids
status
```

`claim_type` 可包括：

- `method`
- `dataset`
- `metric`
- `result`
- `limitation`
- `comparison`
- `implementation`
- `idea`

### 5.5 Evidence

代表支持 claim 的证据。

字段建议：

```text
id
claim_id
source_type
source_url
paper_id
section
quote
normalized_text
confidence
verification_status
created_at
```

`Evidence` 是整个系统最关键的模型。以后所有进入最终报告的核心结论，都必须能追溯到 evidence。

### 5.6 MethodTaxonomy

代表技术谱系。

字段建议：

```text
id
project_id
nodes
edges
summary
open_problems
```

节点类型：

- task
- dataset
- method family
- model architecture
- training recipe
- evaluation protocol
- limitation
- open problem

### 5.7 BaselineCandidate

代表一个可复现 baseline。

字段建议：

```text
id
project_id
name
paper_id
method_summary
code_url
dataset
metric
reported_score
reproduction_difficulty
hardware_requirement
expected_runtime
license
rank_score
selection_reason
status
```

### 5.8 ResearchIdea

代表一个候选研究 idea。

字段建议：

```text
id
project_id
title
motivation
core_hypothesis
method_sketch
expected_advantage
required_baselines
required_datasets
evaluation_plan
novelty_score
feasibility_score
risk_score
overall_score
evidence_ids
status
```

### 5.9 ExperimentSpec

代表实验设计。

字段建议：

```text
id
project_id
idea_id
baseline_id
task
dataset
metrics
train_command
eval_command
config
expected_outputs
hardware_requirement
seed_plan
ablation_plan
```

### 5.10 ExperimentRun

代表一次实验运行。

字段建议：

```text
id
experiment_spec_id
status
started_at
ended_at
command
exit_code
stdout_path
stderr_path
metrics
artifacts
failure_reason
```

### 5.11 CodeArtifact

代表生成或采集的代码资产。

字段建议：

```text
id
project_id
artifact_type
path
language
source
related_baseline_id
related_idea_id
checksum
created_at
```

## 6. 事件协议

必须把当前松散的 `StreamEvent` 改成类型化事件。

建议后端使用 Pydantic discriminated union，前端使用 TS/Zod 同构定义。

短期可手写同构 Zod，不急着引入 codegen。等事件协议稳定后，再考虑自动生成。

核心事件类型：

```text
status
plan
plan_review_required
plan_review_approved
tool_call
tool_observation
paper_found
paper_screened
paper_read
claim_extracted
evidence_verified
taxonomy_updated
baseline_candidate
baseline_review_required
baseline_selected
idea_generated
idea_ranked
experiment_spec_created
experiment_approval_required
experiment_run_started
experiment_run_finished
artifact_created
report_section
done
error
cancelled
usage
```

每个事件都应包含：

```text
task_id
seq
type
timestamp
payload
```

要求：

- `type` 必须是枚举或 literal。
- `payload` 必须按事件类型定义 schema。
- 前端不再直接 switch 一个松散 dict。
- 后端新增事件时，必须补前端 schema 和 contract test。

## 7. Agent Runtime

新的执行方式不是固定 pipeline，而是 LangGraph 状态图：

```text
User Goal
  -> PlannerAgent
  -> Plan Review
  -> Agent Loop
      -> select tool
      -> execute tool
      -> record observation
      -> update research state
      -> request approval if needed
  -> generate artifacts
  -> final audit
  -> final report
```

编排约束：

- LangGraph 是生产默认路径。
- `ResearchState` 仍是运行时业务状态的唯一所有者。
- LangGraph 只持有一个轻量 envelope，不复制、不枚举业务状态字段。
- agent node 通过适配器接入图，不在图定义里手写状态同步逻辑。
- 手写 runner 只用于兼容旧任务和定位回归问题。

### 7.1 Agent Loop 要求

agent loop 必须支持：

- 最大迭代次数
- 最大工具调用次数
- token budget
- cost budget
- tool call validation
- approval pause/resume
- error recovery
- observation truncation
- context compaction
- loop repetition detection
- cancellation

### 7.2 Agent State

建议维护统一 `ResearchState`：

```text
project
plan
papers
paper_notes
claims
evidence
taxonomy
baselines
ideas
experiment_specs
experiment_runs
artifacts
review_decisions
tool_trace
```

不要把所有中间状态塞进 Markdown。

## 8. 工具协议

引入统一工具协议：

```text
ToolSpec
ToolCall
ToolResult
ToolObservation
ToolRouter
ApprovalPolicy
```

### 8.1 ToolSpec

```text
name
description
parameters_schema
permission_level
timeout_seconds
cost_level
handler
```

### 8.2 ToolCall

```text
id
task_id
tool_name
arguments
requested_by
created_at
approval_status
```

### 8.3 ToolObservation

```text
id
tool_call_id
status
summary
raw_output_ref
structured_output
error
created_at
```

### 8.4 Permission Level

建议分级：

```text
read_only
network_read
write_artifact
write_repo
run_local_command
run_expensive_job
external_side_effect
destructive
```

默认规则：

- `read_only` 自动执行。
- `network_read` 可自动执行，但需要 cost/rate limit。
- `write_artifact` 可自动执行，但要保留 diff。
- `write_repo` 需要审批。
- `run_local_command` 需要审批。
- `run_expensive_job` 需要审批。
- `external_side_effect` 需要审批。
- `destructive` 默认禁止，除非用户显式授权。

## 9. 第一批工具

### 9.1 文献工具

- `paper_search`
- `paper_details`
- `paper_read`
- `citation_graph`
- `paper_recommend`
- `paper_screen`

### 9.2 Evidence 工具

- `claim_extract`
- `evidence_extract`
- `evidence_verify`
- `citation_audit`

### 9.3 技术谱系工具

- `taxonomy_build`
- `taxonomy_update`
- `taxonomy_compare`

### 9.4 Baseline 工具

- `baseline_extract`
- `baseline_rank`
- `baseline_feasibility_check`
- `dataset_availability_check`
- `code_availability_check`

### 9.5 代码工具

- `github_code_search`
- `repo_file_list`
- `repo_file_read`
- `code_summarize`
- `code_artifact_write`
- `code_patch`

### 9.6 实验工具

- `experiment_spec_generate`
- `experiment_config_write`
- `experiment_run_prepare`
- `test_run`
- `metric_parse`
- `artifact_collect`

## 10. Agent 分工

不要继续堆泛化 agent 名称。按职责拆。

### 10.1 PlannerAgent

输入用户目标，输出研究计划。

产物：

- research questions
- search strategy
- inclusion/exclusion criteria
- expected artifacts
- review checkpoints

### 10.2 PaperCollectorAgent

负责找论文。

产物：

- paper candidates
- screening reason
- citation graph seed
- related work clusters

### 10.3 PaperReaderAgent

负责读论文关键部分。

产物：

- structured paper note
- method summary
- experiment setup
- result table
- limitation summary

### 10.4 EvidenceExtractorAgent

负责抽取 claim 和 evidence。

产物：

- claim list
- evidence list
- verification status

### 10.5 TaxonomyAgent

负责技术谱系。

产物：

- method families
- method evolution path
- dataset/evaluation map
- unresolved problems

### 10.6 BaselineSelectorAgent

负责选择 baseline。

产物：

- baseline candidates
- ranking
- reproduction difficulty
- selected baseline

### 10.7 IdeaGeneratorAgent

负责生成 idea。

产物：

- idea candidates
- novelty assessment
- feasibility assessment
- experiment plan

### 10.8 CodeScoutAgent

负责找代码。

产物：

- repo candidates
- implementation notes
- API usage patterns
- missing pieces

### 10.9 ReproducerAgent

负责生成 baseline 复现工程。

产物：

- baseline code
- config
- README
- reproduce command
- evaluation script

### 10.10 ExperimentDesignerAgent

负责 proposed method 实验框架。

产物：

- proposed method skeleton
- config
- ablation design
- metrics parser
- run scripts

### 10.11 ReviewerAgent

负责审查。

产物：

- evidence gaps
- unsupported claims
- weak baseline warning
- experiment design risk
- final audit report

## 11. 人在回路

生产级版本至少要阻塞三类节点。

### 11.1 Plan Review

研究计划未批准，不开始正式调研。

前端需要展示：

- 研究问题
- 搜索策略
- inclusion/exclusion criteria
- 预计产物
- 成本和时间估计

用户可以：

- approve
- request changes
- cancel

### 11.2 Baseline Selection Review

baseline 未确认，不生成复现代码。

前端需要展示：

- baseline 排名
- 每个 baseline 的论文证据
- 代码可用性
- 数据集可用性
- 复现难度
- 硬件要求

### 11.3 Experiment Execution Review

涉及本地命令、GPU、外部 API、写 repo 的操作，必须审批。

前端需要展示：

- command
- working directory
- expected output
- estimated cost
- files to be written
- risk level

### 11.4 Citation Review

Citation Review 建议分两层：

- 自动 evidence check：每次 claim 产生时检查。
- 最终 citation audit：报告生成后统一复核。

不要只在最后才发现引用不可靠。

## 12. 前端工作台

### 12.1 Overview

展示项目总览：

- 当前阶段
- 关键产物
- review checkpoint
- cost
- progress
- latest events

### 12.2 Literature

展示论文库：

- paper table
- screening status
- relevance score
- citation count
- code availability
- dataset mentions
- reading status

### 12.3 Taxonomy

展示技术谱系：

- method families
- timeline
- dataset/method/result map
- open problems

### 12.4 Baselines

展示 baseline 候选：

- ranking
- score
- reproduction difficulty
- code URL
- dataset
- metric
- selection reason

### 12.5 Ideas

展示 idea 候选：

- novelty score
- feasibility score
- risk score
- supporting evidence
- required experiments

### 12.6 Experiments

展示实验：

- specs
- configs
- run status
- logs
- metrics
- artifacts

### 12.7 Artifacts

展示生成资产：

- Markdown
- JSON
- CSV
- code files
- config files
- logs

### 12.8 Trace

展示 agent 轨迹：

- agent message
- tool call
- tool observation
- approval event
- error event
- retry event

Trace 是调试和建立用户信任的核心页面，不是可有可无。

## 13. 实验目录规范

每个研究项目生成独立实验目录。

```text
experiments/
  <project_slug>/
    README.md
    papers/
      paper_matrix.csv
      taxonomy.json
    baselines/
      <baseline_name>/
        README.md
        requirements.txt
        config.yaml
        train.py
        eval.py
        reproduce.sh
        results.json
    proposed/
      <method_name>/
        README.md
        requirements.txt
        config.yaml
        train.py
        eval.py
        ablation.yaml
        run.sh
    runs/
      <run_id>/
        stdout.log
        stderr.log
        metrics.json
        artifacts/
```

每个 baseline 必须包含：

- 方法来源
- 论文引用
- 数据集
- 指标
- 原论文结果
- 预期复现结果
- 运行命令
- 环境依赖
- 硬件要求

每个 proposed method 必须包含：

- 核心假设
- 相比 baseline 的变化
- 训练脚本
- 评估脚本
- ablation plan
- failure analysis plan

## 14. 分阶段路线

## Phase 1：研究资产模型与类型化事件

目标：把“报告字符串”变成“结构化研究资产”。

交付：

- Pydantic domain models
- SQLite schema
- typed `StreamEvent`
- 前端 TS/Zod schema
- event handler map
- `ResearchProject` 基础 CRUD
- `Paper / Claim / Evidence / Baseline / Idea / Experiment` 基础存储
- contract tests

验收标准：

- 后端无法发送未知事件类型。
- 前端无法静默吞掉未知 payload。
- 一个 task 能写入并回放完整 typed event stream。
- 旧报告流程仍可运行，但产物开始写入结构化表。

## Phase 2：Agent Runtime 与 ToolRouter

目标：把固定 pipeline 改成基于 LangGraph 的可循环 agent runtime。

交付：

- LangGraph runtime graph
- node adapter / graph state envelope
- `ToolSpec`
- `ToolRouter`
- `ToolCall`
- `ToolObservation`
- `ApprovalPolicy`
- runtime session
- pause/resume
- trace storage
- trace 页面基础版

验收标准：

- agent 能多轮选择工具并读取 observation。
- 每次工具调用都能在前端 trace 页面看到。
- 需要审批的工具会真正暂停。
- 用户批准后任务能继续执行。
- 用户拒绝后任务能安全降级或结束。

## Phase 3：文献调研与 Evidence Graph

目标：完成严肃 literature survey 的基础闭环。

交付：

- `paper_search`
- `paper_read`
- `citation_graph`
- `claim_extract`
- `evidence_verify`
- paper matrix
- literature 页面
- evidence graph 基础版

验收标准：

- 能从一个研究问题生成候选论文集。
- 能筛选论文并给出筛选理由。
- 能读取论文方法和实验部分。
- 能抽取 claim/evidence。
- 每个关键结论能追溯到论文来源。

## Phase 4：技术谱系、Baseline 与 Idea

目标：从调研结果生成可执行的研究方向。

交付：

- taxonomy builder
- baseline extractor
- baseline ranker
- code availability checker
- dataset availability checker
- idea generator
- idea ranker
- taxonomy/baselines/ideas 页面

验收标准：

- 能展示技术谱系。
- 能列出至少 3 个 baseline 候选。
- 每个 baseline 有复现难度、代码可用性、数据集可用性。
- 能生成多条 idea，并按 novelty/feasibility/risk 排名。
- baseline 选择前必须经过人工确认。

## Phase 5：Baseline 复现代码与实验框架

目标：生成可运行的 baseline 复现工程和 proposed method 框架。

交付：

- GitHub code search
- repo reader
- code artifact writer
- baseline reproduction generator
- proposed method scaffold generator
- experiment spec generator
- test runner
- experiment 页面
- artifact 页面

验收标准：

- 选定 baseline 后能生成标准实验目录。
- 能生成 `README.md`、`requirements.txt`、`config.yaml`、`train.py`、`eval.py`、`reproduce.sh`。
- 能生成 proposed method scaffold。
- 本地命令运行必须经过审批。
- 实验结果能写入 `metrics.json` 并在前端展示。

## Phase 6：生产化治理

目标：让系统可以长期稳定使用。

交付：

- durable task runtime
- resumable task
- cost budget
- rate limit
- context compaction
- tool timeout
- retry policy
- artifact versioning
- audit log
- permission policy
- project export/import

验收标准：

- 后端重启后任务状态不会丢失。
- 长任务可以恢复。
- 所有高风险工具调用都有审计记录。
- 报告、代码、实验结果可以完整导出。

## 15. 生产质量门槛

上线前必须满足：

- 后端单元测试覆盖 domain model 和 event schema。
- 前后端事件 contract test 通过。
- 所有工具都有 timeout。
- 所有工具调用都有 trace。
- 所有写文件操作都有 artifact record。
- 所有本地命令执行都需要审批。
- 所有最终报告 claim 都能关联 evidence，或者明确标注 unsupported。
- 前端未知事件不能导致白屏。
- 任务失败必须有可读错误和恢复建议。

## 16. 与现有代码的映射

### 可复用

- FastAPI 应用结构
- SSE 任务流
- SQLite store
- Settings
- Task history
- Knowledge 页面思路
- Citation check 页面思路
- Markdown report renderer
- Cost dashboard
- Vue AppShell

### 需要重构

- `schemas.py` 中的 loose event schema
- `main_graph.py` 的固定流程
- `human_review.py` 的自动 approve
- `citation_review.py` 的事后式 review
- 前端 task store 的长 `if/else`
- 大型 Vue view 文件

### 需要新增

- `research/domain`
- `research/runtime`
- `research/tools`
- `research/artifacts`
- `research/governance`
- `research/events`
- 前端 project workspace routes

## 17. 第一批工程 Issue

建议按下面顺序开工：

1. 新增 `ResearchProject`、`Paper`、`Claim`、`Evidence`、`BaselineCandidate`、`ResearchIdea`、`ExperimentSpec` 模型。
2. 新增 SQLite 表和 store 方法。
3. 把 `StreamEvent` 改成 Pydantic discriminated union。
4. 前端新增 Zod discriminated union。
5. 前端 `applyEvent` 改成 handler map。
6. 新增 contract test，确保后端事件和前端 schema 对齐。
7. 新增 `ToolSpec`、`ToolRouter`、`ToolCall`、`ToolObservation`。
8. 新增只读工具 `paper_search` 的 skeleton。
9. 新增 trace event 和 trace storage。
10. 新增 Plan Review 真阻塞。
11. 新增 `ResearchProject` 页面基础路由。
12. 新增 Literature 页面基础表格。
13. 新增 `PaperMatrix` artifact。
14. 新增 `claim_extract` skeleton。
15. 新增 evidence completeness check。

## 18. 不做什么

短期不要做：

- 不要继续堆新的展示页面但不改底层模型。
- 不要继续让 agent 输出大段 Markdown 再由前端展示。
- 不要让工具直接返回不可追踪文本。
- 不要让本地命令自动执行。
- 不要一开始就做复杂 codegen。
- 不要一开始就接大型任务队列，SQLite + durable runtime 可以先撑住。
- 不要把 citation review 只放在报告最后。

## 19. 最终形态

用户输入：

```text
我想做 code generation / RAG / LLM evaluation / multimodal / GNN / agent 方向的研究。
请帮我完成文献调研，梳理技术谱系，选择 baseline，提出 idea，并生成复现实验框架。
```

系统输出：

```text
1. 论文库
2. 论文矩阵
3. 技术谱系
4. baseline 排名
5. idea 排名
6. evidence graph
7. baseline 复现代码
8. proposed method 实验框架
9. 实验配置与运行日志
10. 最终研究报告
```

这才是 Athena 应该升级成的方向。
