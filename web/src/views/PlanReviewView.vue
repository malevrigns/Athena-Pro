<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Document, Bell, CopyDocument, Warning, Check, Edit, Close,
  EditPen, Picture, Connection, Promotion,
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import EChart from '@/components/charts/EChart.vue'
import { useTaskStore } from '@/stores/task'
import { costApi, interruptTask, submitReview, type CostByModel, type CostByNode, type CostSummary, type CostTrend } from '@/api/client'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.pr-head, .pr-editor, .pr-cost', { delay: (_el, i) => 100 + i * 100 })
useEntrance('.pr-step', { delay: (_el, i) => 200 + i * 60 })
useEntrance('.pr-cost-kpi, .pr-chart', { delay: (_el, i) => 350 + i * 80 })

const router = useRouter()
const task = useTaskStore()
const activeStep = ref(0)

import { watch } from 'vue'

onMounted(async () => {
  if (!task.tasks.length) await task.refreshTasks()
  // Pick a task awaiting review (planning / waiting_review). Fallback to current.
  if (!task.current?.plan) {
    const pending = task.tasks.find((t) =>
      ['planning', 'waiting_review'].includes(t.status) && t.plan,
    ) || task.tasks.find((t) => t.plan)
    if (pending) await task.load(pending.id, false)
  }
  await loadCost()
})
watch(() => task.current?.id, () => loadCost())

const taskMeta = computed(() => task.current)
const plan = computed(() => task.plan)
const steps = computed(() =>
  (plan.value?.topics ?? []).map((t, i) => ({ n: i + 1, label: t.title, id: t.id, topic: t })),
)
const activeTopic = computed(() => steps.value[activeStep.value]?.topic)
const budget = computed(() => taskMeta.value?.cost_usd ? taskMeta.value.cost_usd * 5 : 50)
const usedCost = computed(() => taskMeta.value?.cost_usd ?? 0)
const usedPct = computed(() => Math.min(100, (usedCost.value / Math.max(0.01, budget.value)) * 100))

async function copyTaskId() {
  if (!taskMeta.value?.id) return
  await navigator.clipboard.writeText(taskMeta.value.id)
  ElMessage.success('Task ID 已复制')
}

async function approve() {
  if (!task.current?.id) return
  try {
    await submitReview(task.current.id, { approved: true, reviewer: 'human', comments: '已批准' })
    ElMessage.success('已批准计划')
    await task.load(task.current.id, false)
  } catch (e) { ElMessage.error((e as Error).message) }
}

async function reject() {
  if (!task.current?.id) return
  try {
    await ElMessageBox.confirm('确定驳回并中断此任务?', '驳回重做', { type: 'warning' })
    await submitReview(task.current.id, { approved: false, reviewer: 'human', comments: '驳回重做' })
    await interruptTask(task.current.id)
    ElMessage.warning('已驳回并中断任务')
    router.push('/history')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

// ----- Edit-and-continue dialog -----
const editDialog = ref(false)
const editTopics = ref<{ id: string; title: string; question: string; rationale: string; search_queries: string }[]>([])

function openEditDialog() {
  if (!plan.value) return
  editTopics.value = plan.value.topics.map((t) => ({
    id: t.id, title: t.title, question: t.question,
    rationale: t.rationale || '', search_queries: t.search_queries.join(', '),
  }))
  editDialog.value = true
}

async function submitEdit() {
  if (!task.current?.id) return
  const revised = editTopics.value.map((t) => ({
    id: t.id,
    title: t.title,
    question: t.question,
    rationale: t.rationale,
    search_queries: t.search_queries.split(/[,, ]+/).map((s) => s.trim()).filter(Boolean),
    priority: 1,
  }))
  try {
    await submitReview(task.current.id, { approved: true, reviewer: 'human', comments: '已修改主题', revised_topics: revised })
    ElMessage.success('已提交修改后的方案')
    editDialog.value = false
    await task.load(task.current.id, false)
  } catch (e) { ElMessage.error((e as Error).message) }
}

function addTopic() {
  editTopics.value.push({ id: `topic_${Math.random().toString(36).slice(2, 8)}`, title: '', question: '', rationale: '', search_queries: '' })
}
function removeTopic(i: number) { editTopics.value.splice(i, 1) }

// ----- Real-time cost data from /v1/cost/*?task_id= -----
const costSummary = ref<CostSummary | null>(null)
const costTrend = ref<CostTrend | null>(null)
const costByModel = ref<CostByModel | null>(null)
const costByNode = ref<CostByNode | null>(null)
const palette = ['#2563eb', '#16a34a', '#f97316', '#facc15', '#a78bfa', '#94a3b8']

async function loadCost() {
  if (!task.current?.id) return
  try {
    const [s, t, m, n] = await Promise.all([
      costApi.summary('all', task.current.id),
      costApi.trend('all', 'day', task.current.id),
      costApi.byModel('all', task.current.id),
      costApi.byNode('all', 5, task.current.id),
    ])
    costSummary.value = s; costTrend.value = t; costByModel.value = m; costByNode.value = n
  } catch (err) { /* ignore — UI shows empty */ }
}

const kpis = computed(() => {
  const topicCount = plan.value?.topics?.length ?? 0
  return [
    { label: '预估总成本', value: '$' + (plan.value?.estimated_cost_usd ?? 0).toFixed(2), unit: 'USD' },
    { label: '研究主题',   value: String(topicCount),                                     unit: 'Topics' },
    { label: '搜索查询',   value: String((plan.value?.topics ?? []).reduce((s, t) => s + t.search_queries.length, 0)), unit: 'Queries' },
    { label: '当前阶段',   value: String(task.status || '—'),                              unit: '' },
  ]
})

const trendOption = computed(() => ({
  grid: { left: 36, right: 16, top: 26, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: costTrend.value?.labels ?? [],
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 10 },
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } },
    axisLine: { show: false }, axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
  },
  series: [{
    type: 'line', smooth: true,
    data: costTrend.value?.values ?? [],
    symbol: 'circle', symbolSize: 6,
    itemStyle: { color: '#2563eb' },
    lineStyle: { width: 2 },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(37,99,235,.16)' }, { offset: 1, color: 'rgba(37,99,235,0)' }] } },
  }],
}))

const pieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { show: false },
  series: [{
    type: 'pie',
    radius: ['55%', '82%'],
    label: { show: false },
    labelLine: { show: false },
    data: (costByModel.value?.items ?? []).map((it, i) => ({
      value: it.cost_usd,
      name: it.model || 'unknown',
      itemStyle: { color: palette[i % palette.length] },
    })),
  }],
}))

const nodeBarOption = computed(() => {
  const items = costByNode.value?.items ?? []
  return {
    grid: { left: 100, right: 56, top: 10, bottom: 30 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } },
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    yAxis: {
      type: 'category', inverse: true,
      data: items.map((i) => i.node || 'unknown'),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#475569', fontSize: 11 },
    },
    series: [{
      type: 'bar', barWidth: 12,
      data: items.map((i) => i.cost_usd),
      itemStyle: { color: '#2563eb', borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: '#0f172a', fontSize: 11, formatter: (p: any) => '$' + Number(p.value).toFixed(4) },
    }],
  }
})

const costRows = computed(() => {
  const items = costByNode.value?.items ?? []
  const total = costSummary.value?.total_cost_usd || 0
  return items.map((it) => ({
    node: it.node || 'unknown',
    cost: '$' + it.cost_usd.toFixed(4),
    pct: total > 0 ? ((it.cost_usd / total) * 100).toFixed(1) + '%' : '—',
    tokens: (it.input_tokens + it.output_tokens).toLocaleString(),
    model: '—',
  }))
})
</script>

<template>
  <div class="pr">
    <ElEmpty v-if="!plan" description="尚无待审查计划。前往「研究台」启动任务,Planner 输出计划后会在这里展示。">
      <ElButton type="primary" :icon="Promotion" @click="router.push('/')">开始研究</ElButton>
    </ElEmpty>

    <template v-else>
    <!-- Header card -->
    <section class="card pr-head">
      <div class="pr-head-left">
        <div class="pr-icon"><ElIcon><Document /></ElIcon></div>
        <div class="pr-meta">
          <h2>{{ taskMeta?.question || plan.question }}</h2>
          <div class="pr-meta-row">
            <span>任务 ID:<code>{{ taskMeta?.id }}</code></span>
            <ElIcon class="copy-ico" @click="copyTaskId"><CopyDocument /></ElIcon>
          </div>
          <div class="pr-meta-row">
            <span v-if="taskMeta?.created_at">📅 创建时间:{{ new Date(taskMeta.created_at).toLocaleString('zh-CN') }}</span>
          </div>
          <div class="pr-meta-row">
            <span v-if="taskMeta?.updated_at">⏱ 最近更新:{{ new Date(taskMeta.updated_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
      </div>
      <div class="pr-head-mid">
        <div class="pr-budget-label">预算</div>
        <div class="pr-budget-value">${{ budget.toFixed(2) }}<small>USD</small></div>
        <div class="pr-budget-used">已用:<b class="primary">${{ usedCost.toFixed(4) }} ({{ usedPct.toFixed(0) }}%)</b></div>
      </div>
      <div class="pr-head-alert">
        <div class="alert-ico"><ElIcon color="#f59e0b"><Warning /></ElIcon></div>
        <div>
          <strong>{{ task.status === 'waiting_review' ? '计划待审查' : '当前阶段:' + task.status }}</strong>
          <p v-if="task.status === 'waiting_review'">点击批准后,Researcher 开始并行调研</p>
          <p class="alert-sub" v-else>当前任务已通过 Plan Review 阶段</p>
        </div>
      </div>
    </section>

    <!-- 2-col body -->
    <div class="pr-grid">
      <!-- Plan review editor -->
      <article class="card pr-editor">
        <header class="pr-editor-head">
          <h3>方案审查 <span class="ver">版本 1.0</span></h3>
          <span class="submit-time">提交时间:2025-05-10 09:20</span>
        </header>
        <div class="pr-editor-body">
          <aside class="pr-steps">
            <div
              v-for="(s, i) in steps" :key="s.n"
              class="pr-step" :class="{ active: activeStep === i }"
              @click="activeStep = i"
            >
              <span class="pr-step-n">{{ s.n }}</span>
              <span class="pr-step-label">{{ s.label }}</span>
            </div>
          </aside>
          <div class="pr-rich">
            <div class="pr-toolbar">
              <button>正文 ▾</button>
              <button><b>B</b></button>
              <button>I</button>
              <button>U</button>
              <span class="sep" />
              <button>≡</button>
              <button>≣</button>
              <span class="sep" />
              <button>🔗</button>
              <button><ElIcon><Picture /></ElIcon></button>
              <button>⊞</button>
              <span class="sep" />
              <button>↶</button>
              <button>↷</button>
            </div>
            <div class="pr-doc" v-if="activeTopic">
              <h4>主题</h4>
              <p><b>{{ activeTopic.title }}</b></p>
              <h4>调研问题</h4>
              <p>{{ activeTopic.question }}</p>
              <h4>动机</h4>
              <p>{{ activeTopic.rationale || '—' }}</p>
              <h4>检索查询</h4>
              <ul>
                <li v-for="q in activeTopic.search_queries" :key="q"><code>{{ q }}</code></li>
              </ul>
              <h4>优先级</h4>
              <p>P{{ activeTopic.priority }}</p>
              <h4>全局假设与成功标准</h4>
              <ul>
                <li v-for="(a, i) in plan.assumptions" :key="'a' + i"><b>假设:</b>{{ a }}</li>
                <li v-for="(c, i) in plan.success_criteria" :key="'c' + i"><b>成功标准:</b>{{ c }}</li>
              </ul>
            </div>
            <ElEmpty v-else :image-size="64" description="选中左侧主题查看详情" />
          </div>
        </div>
        <div class="pr-actions">
          <button class="btn-approve" @click="approve"><ElIcon><Check /></ElIcon><span>批准</span></button>
          <button class="btn-edit" @click="openEditDialog"><ElIcon><Edit /></ElIcon><span>修改后继续</span></button>
          <button class="btn-reject" @click="reject"><ElIcon><Close /></ElIcon><span>驳回重做</span></button>
        </div>
      </article>

      <!-- Cost & quality overview -->
      <article class="card pr-cost">
        <header class="pr-cost-head">
          <h3>成本与质量概览</h3>
        </header>
        <div class="pr-cost-kpis">
          <div v-for="(k, i) in kpis" :key="i" class="pr-cost-kpi">
            <div class="kpi-label">{{ k.label }}</div>
            <div class="kpi-value">{{ k.value }}<small>{{ k.unit }}</small></div>
          </div>
        </div>

        <div class="pr-cost-alert" v-if="usedPct >= 25">
          <ElIcon color="#f59e0b"><Warning /></ElIcon>
          <span>预算使用率 {{ usedPct.toFixed(0) }}%,部分环节成本较高,建议关注模型使用效率。</span>
          <a>查看建议 ›</a>
        </div>

        <div class="pr-cost-charts">
          <div class="pr-chart">
            <header><h4>月度成本趋势 (预估)</h4><small>USD</small></header>
            <EChart :option="trendOption" height="180px" />
          </div>
          <div class="pr-chart">
            <header><h4>模型成本分布 (预估)</h4></header>
            <div class="donut-block">
              <EChart :option="pieOption" height="180px" />
              <div class="donut-center">
                <span class="dc-lbl">预估总计</span>
                <span class="dc-val">${{ (plan.estimated_cost_usd ?? 0).toFixed(2) }}</span>
              </div>
            </div>
            <p class="muted-line">示意:实际模型分布将在任务运行后基于真实 Token 用量计算</p>
          </div>
        </div>

        <div class="pr-chart" style="margin-top: 16px;">
          <header><h4>节点成本排名 (预估 Top 5)</h4><small>USD</small></header>
          <EChart :option="nodeBarOption" height="200px" />
        </div>

        <div class="pr-table">
          <header><h4>成本明细 (预估)</h4></header>
          <div class="th-row">
            <div>节点</div>
            <div>预估成本 (USD)</div>
            <div>占比</div>
            <div>预估用量 (Tokens)</div>
            <div>主要模型</div>
          </div>
          <div v-for="(r, i) in costRows" :key="i" class="td-row">
            <div>{{ r.node }}</div>
            <div class="mono">{{ r.cost }}</div>
            <div>{{ r.pct }}</div>
            <div class="mono">{{ r.tokens }}</div>
            <div class="muted">{{ r.model }}</div>
          </div>
          <div class="td-row total" v-if="costRows.length">
            <div><b>合计</b></div>
            <div class="mono"><b>${{ (plan.estimated_cost_usd ?? 0).toFixed(2) }}</b></div>
            <div><b>100%</b></div>
            <div class="mono"><b>{{ costRows.reduce((s, r) => s + parseInt(r.tokens.replace(/,/g, '')), 0).toLocaleString() }}</b></div>
            <div class="muted">—</div>
          </div>
        </div>
      </article>
    </div>
    </template>

    <ElDialog v-model="editDialog" title="修改方案后继续" width="720px">
      <div class="edit-list">
        <div v-for="(t, i) in editTopics" :key="t.id" class="edit-card">
          <header>
            <strong>主题 {{ i + 1 }}</strong>
            <button class="btn-icon-danger" @click="removeTopic(i)" title="删除">×</button>
          </header>
          <ElForm label-position="top">
            <ElFormItem label="标题">
              <ElInput v-model="t.title" placeholder="主题标题" />
            </ElFormItem>
            <ElFormItem label="调研问题">
              <ElInput v-model="t.question" type="textarea" :rows="2" placeholder="具体问题" />
            </ElFormItem>
            <ElFormItem label="动机">
              <ElInput v-model="t.rationale" placeholder="为什么要查这个" />
            </ElFormItem>
            <ElFormItem label="搜索查询 (逗号分隔)">
              <ElInput v-model="t.search_queries" placeholder="query1, query2, query3" />
            </ElFormItem>
          </ElForm>
        </div>
        <ElButton plain :icon="Edit" @click="addTopic">+ 添加主题</ElButton>
      </div>
      <template #footer>
        <ElButton @click="editDialog = false">取消</ElButton>
        <ElButton type="primary" @click="submitEdit">提交修改</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.pr { display: grid; gap: 16px; }

/* Header */
.pr-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px 280px;
  gap: 22px;
  padding: 18px 22px;
  align-items: center;
}
.pr-head-left { display: flex; gap: 14px; align-items: flex-start; }
.pr-icon {
  width: 50px; height: 50px;
  border-radius: 10px;
  background: #dbeafe;
  color: #2563eb;
  display: grid; place-items: center;
  flex-shrink: 0;
}
.pr-icon .el-icon { font-size: 22px; }
.pr-meta h2 { margin: 0 0 6px; font-size: 18px; font-weight: 700; color: var(--text); letter-spacing: -.01em; }
.pr-meta-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: var(--muted);
  margin-top: 2px;
}
.pr-meta-row code {
  font-family: var(--t-mono); font-size: 12px;
  color: var(--text-soft);
}
.copy-ico { color: var(--muted-soft); cursor: pointer; font-size: 13px; }
.copy-ico:hover { color: var(--primary); }

.pr-head-mid { display: grid; gap: 4px; }
.pr-budget-label { font-size: 12.5px; color: var(--muted); }
.pr-budget-value { font-size: 28px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; }
.pr-budget-value small { font-size: 12px; color: var(--muted); font-weight: 500; margin-left: 6px; }
.pr-budget-used { font-size: 12px; color: var(--muted); }
.pr-budget-used .primary { color: var(--primary); font-weight: 600; }

.pr-head-alert {
  display: flex; gap: 10px;
  padding: 12px 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
}
.alert-ico { flex-shrink: 0; padding-top: 2px; }
.alert-ico .el-icon { font-size: 16px; }
.pr-head-alert strong { font-size: 13px; color: var(--orange-text); font-weight: 600; display: block; }
.pr-head-alert p { margin: 4px 0 0; font-size: 12px; color: var(--text-soft); }
.pr-head-alert p b { color: var(--orange-text); }
.alert-sub { color: var(--muted) !important; font-size: 11px !important; }

/* Grid */
.pr-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 16px;
  align-items: start;
}

/* Editor */
.pr-editor { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.pr-editor-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}
.pr-editor-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }
.ver {
  font-size: 11px; padding: 1px 8px;
  background: var(--primary-soft);
  color: var(--primary);
  border-radius: 999px;
  margin-left: 6px;
  font-weight: 600;
}
.submit-time { font-size: 12px; color: var(--muted); font-family: var(--t-mono); }
.pr-editor-body {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 14px;
  padding: 14px;
  flex: 1;
}

.pr-steps { display: grid; gap: 4px; }
.pr-step {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--text-soft);
  cursor: pointer;
}
.pr-step:hover { background: var(--surface-2); }
.pr-step.active {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}
.pr-step-n {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--surface-3);
  color: var(--muted);
  display: grid; place-items: center;
  font-size: 11px; font-weight: 700; font-family: var(--t-mono);
  flex-shrink: 0;
}
.pr-step.active .pr-step-n {
  background: var(--primary);
  color: white;
}

.pr-rich {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.pr-toolbar {
  display: flex; align-items: center; gap: 4px;
  padding: 8px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}
.pr-toolbar button {
  width: 28px; height: 28px;
  border: none; background: transparent;
  color: var(--text-soft);
  cursor: pointer; border-radius: 5px;
  font: inherit; font-size: 12px;
}
.pr-toolbar button:hover { background: var(--surface-3); color: var(--primary); }
.pr-toolbar button:first-child { width: auto; padding: 0 8px; }
.pr-toolbar .sep { width: 1px; height: 18px; background: var(--border); margin: 0 4px; }

.pr-doc {
  padding: 16px 20px;
  font-size: 13px;
  line-height: 1.85;
  color: var(--text-soft);
  max-height: 560px;
  overflow: auto;
}
.pr-doc h4 { margin: 12px 0 8px; font-size: 14px; font-weight: 700; color: var(--text); }
.pr-doc h4:first-child { margin-top: 0; }
.pr-doc ul, .pr-doc ol { margin: 4px 0 8px; padding-left: 20px; }
.pr-doc li { margin: 4px 0; }
.pr-doc li b { color: var(--text); font-weight: 600; }

.pr-actions {
  display: flex; gap: 12px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}
.btn-approve, .btn-edit, .btn-reject {
  display: inline-flex; align-items: center; gap: 6px;
  height: 38px; padding: 0 18px;
  border-radius: 8px;
  font: inherit; font-size: 13.5px; font-weight: 600;
  cursor: pointer;
  border: 1px solid;
}
.btn-approve { background: var(--green); border-color: var(--green); color: white; }
.btn-approve:hover { background: #15803d; }
.btn-edit { background: var(--surface); color: var(--primary); border-color: var(--primary-line); }
.btn-edit:hover { background: var(--primary-soft); }
.btn-reject { background: var(--surface); color: var(--red); border-color: #fecaca; }
.btn-reject:hover { background: var(--red-soft); }

/* Cost */
.pr-cost { padding: 0; }
.pr-cost-head { padding: 14px 20px; border-bottom: 1px solid var(--border); }
.pr-cost-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }

.pr-cost-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}
.pr-cost-kpi { display: grid; gap: 4px; }
.pr-cost-kpi .kpi-label { font-size: 12px; color: var(--muted); }
.pr-cost-kpi .kpi-value { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -.01em; }
.pr-cost-kpi .kpi-value small { font-size: 11px; color: var(--muted); margin-left: 4px; font-weight: 500; }

.pr-cost-alert {
  display: flex; align-items: center; gap: 8px;
  margin: 12px 20px 0;
  padding: 10px 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--text-soft);
}
.pr-cost-alert span { flex: 1; }
.pr-cost-alert a { color: var(--primary); font-weight: 600; cursor: pointer; font-size: 12.5px; }

.pr-cost-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 14px 20px 0;
}
.pr-chart header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pr-chart h4 { margin: 0; font-size: 13px; font-weight: 600; color: var(--text); }
.pr-chart small { font-size: 11px; color: var(--muted); }

.donut-block { position: relative; }
.donut-center {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}
.dc-lbl { display: block; font-size: 11px; color: var(--muted); }
.dc-val { display: block; font-size: 16px; font-weight: 700; color: var(--text); margin-top: 2px; }
.donut-list { list-style: none; padding: 0; margin: 8px 0 0; display: grid; gap: 4px; }
.donut-list li { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--text-soft); }
.donut-list li b { margin-left: auto; font-weight: 600; color: var(--text); }
.donut-list li small { color: var(--muted-soft); font-size: 11px; }
.donut-list .ld { width: 8px; height: 8px; border-radius: 50%; }

.pr-table { margin: 16px 20px 18px; }
.pr-table header { margin-bottom: 8px; }
.pr-table h4 { margin: 0; font-size: 13px; font-weight: 600; color: var(--text); }
.pr-table .th-row, .pr-table .td-row {
  display: grid;
  grid-template-columns: 1.8fr .8fr .4fr 1fr 1.4fr;
  gap: 10px;
  padding: 8px 10px;
  font-size: 12px;
  align-items: center;
}
.pr-table .th-row {
  background: var(--surface-3);
  color: var(--text-soft);
  font-weight: 600;
  border-radius: 6px 6px 0 0;
}
.pr-table .td-row {
  border-bottom: 1px solid var(--border);
  color: var(--text-soft);
}
.pr-table .td-row:last-child { border-bottom: none; }
.pr-table .td-row.total { background: var(--surface-2); }
.mono { font-family: var(--t-mono); }
.muted { color: var(--muted); }

.edit-list { display: grid; gap: 14px; max-height: 60vh; overflow: auto; padding-right: 4px; }
.edit-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; background: var(--surface-2); }
.edit-card header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.edit-card strong { font-size: 13px; color: var(--text); }
.btn-icon-danger {
  width: 26px; height: 26px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--surface);
  color: var(--red); cursor: pointer; font: inherit; font-size: 14px;
  display: grid; place-items: center;
}
.btn-icon-danger:hover { background: var(--red-soft); border-color: var(--red); }

@media (max-width: 1500px) {
  .pr-cost-charts { grid-template-columns: 1fr; }
}
@media (max-width: 1300px) {
  .pr-head { grid-template-columns: 1fr; }
  .pr-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .pr-cost-kpis { grid-template-columns: 1fr 1fr; }
  .pr-editor-body { grid-template-columns: 1fr; }
}
</style>
