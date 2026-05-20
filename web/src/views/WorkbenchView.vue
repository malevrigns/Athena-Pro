<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  CopyDocument, VideoPause, CircleClose, Check, Document, Reading,
  TrendCharts, OfficeBuilding, Promotion, Search, Connection, ArrowRight,
} from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.wb-head, .wb-steps', { delay: (_el, i) => 60 + i * 80 })
useEntrance('.wb-step', { delay: (_el, i) => 240 + i * 60 })
useEntrance('.wb-col > .card', { delay: (_el, i) => 220 + i * 60 })

const props = defineProps<{ id?: string }>()
const task = useTaskStore()
const session = useSessionStore()
const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

onMounted(() => {
  if (props.id) task.load(props.id)
})
watch(() => props.id, (id) => { if (id) task.load(id) })
onBeforeUnmount(() => task.closeStream())

const steps = [
  { key: 'planner',   label: 'Planner',            statuses: ['planning'] },
  { key: 'review',    label: 'Plan Review',        statuses: ['waiting_review'] },
  { key: 'parallel',  label: 'Parallel Researchers', statuses: ['researching'] },
  { key: 'fact',      label: 'Fact Checker',       statuses: ['quality_gate'] },
  { key: 'citation',  label: 'Citation Validator', statuses: ['quality_gate'] },
  { key: 'writer',    label: 'Writer',             statuses: ['writing'] },
  { key: 'final',     label: 'Final Report',       statuses: ['done'] },
]
const allOrder = ['planner', 'review', 'parallel', 'fact', 'citation', 'writer', 'final']
const currentStepIdx = computed(() => {
  const s = task.status
  if (s === 'planning') return 0
  if (s === 'waiting_review') return 1
  if (s === 'researching') return 2
  if (s === 'quality_gate') return 3
  if (s === 'writing') return 5
  if (s === 'done') return 6
  return 0
})
function stepState(i: number): 'done' | 'current' | 'todo' {
  if (i < currentStepIdx.value) return 'done'
  if (i === currentStepIdx.value) return 'current'
  return 'todo'
}

const taskId = computed(() => task.current?.id || (props.id ?? '—'))
const taskTitle = computed(() => task.current?.question || '尚未选择任务')
const createdAt = computed(() => task.current?.created_at || '—')
const estimatedAt = computed(() => '—')

const progress = computed(() => task.progress)

// Live SSE events
const liveEvents = computed(() => {
  return [...task.events].slice(-10).reverse().map((ev) => {
    const p = ev.payload as Record<string, any>
    let title = ''
    let detail = ''
    let actor = ''
    if (ev.type === 'plan') {
      title = 'Planner 已生成研究计划'; detail = `计划包含 ${(p.plan?.topics?.length ?? 0)} 个核心研究方向`; actor = 'planner'
    } else if (ev.type === 'finding') {
      title = `${ev.node || 'Researcher'} 已完成 ${(p.finding?.sources?.length ?? 0)} 个来源`; detail = (p.finding?.title || ''); actor = 'researcher'
    } else if (ev.type === 'route') {
      title = '协调中'; detail = `iter ${p.iteration} → ${p.route}`; actor = 'supervisor'
    } else if (ev.type === 'quality') {
      title = 'Quality Gate 已评分'; detail = `overall = ${(p.quality?.overall ?? 0).toFixed(2)}`; actor = 'quality'
    } else if (ev.type === 'review') {
      title = 'Reviewer 已审阅'; detail = String(p.review || '').slice(0, 80); actor = 'reviewer'
    } else if (ev.type === 'usage') {
      title = `${p.usage?.node || ''} 用量上报`; detail = `${p.usage?.input_tokens || 0}/${p.usage?.output_tokens || 0} tok`; actor = 'usage'
    } else if (ev.type === 'done') {
      title = '报告已生成'; detail = `${p.final_report?.citations?.length ?? 0} 条引用`; actor = 'writer'
    } else if (ev.type === 'created') {
      title = '任务已启动'; detail = '正在初始化并行研究环境…'; actor = 'system'
    } else if (ev.type === 'status') {
      title = `进入 ${p.status} 阶段`; detail = ''; actor = String(ev.node || 'system')
    } else if (ev.type === 'error') {
      title = '发生错误'; detail = String(p.error || ''); actor = 'system'
    } else {
      title = ev.type; detail = ''; actor = String(ev.node || '')
    }
    return {
      time: formatTime(ev.ts),
      actor,
      title,
      detail,
      type: ev.type,
    }
  })
})

function formatTime(ts?: string): string {
  if (!ts) return '--:--:--'
  try { return new Date(ts).toTimeString().slice(0, 8) } catch { return '--:--:--' }
}

const planSteps = computed(() => {
  const total = task.plan?.topics?.length ?? 0
  return [
    { label: '定义研究范围与核心问题', done: total > 0 },
    { label: '确定研究方法与数据源',  done: total > 0 },
    { label: '生成检索关键词与查询策略', done: total > 0 },
    { label: '制定评估标准与分析框架', done: total > 0 },
    { label: '确认计划并启动研究',    done: task.status !== 'planning' && task.status !== 'created' && total > 0 },
  ]
})

const agentIcons = [Connection, Reading, TrendCharts, Document, Search, Promotion]
const agentColors = ['blue', 'green', 'purple', 'orange', 'pink', 'cyan']

const researcherAgents = computed(() => {
  const topics = task.plan?.topics ?? []
  return topics.map((topic, i) => {
    const matched = task.findings.find((f) => f.topic_id === topic.id)
    const sources = matched?.sources.length ?? 0
    const queries = topic.search_queries?.length || 1
    const totalSteps = queries
    let processed = 0
    let status: 'done' | 'progress' | 'queued' = 'queued'
    let progress = 0
    if (matched) { processed = totalSteps; status = 'done'; progress = 100 }
    else if (task.status === 'researching') {
      processed = Math.floor(totalSteps * 0.4)
      status = 'progress'
      progress = 40
    }
    return {
      name: topic.title,
      icon: agentIcons[i % agentIcons.length],
      color: agentColors[i % agentColors.length],
      total: totalSteps,
      processed,
      collected: sources,
      progress,
      status,
    }
  })
})

const reportHtml = computed(() => {
  const raw = task.finalReport?.markdown || task.writerStream || ''
  if (!raw) return ''
  return DOMPurify.sanitize(md.render(raw))
})

const tokenUsed = computed(() => {
  const usage = task.events
    .filter((e) => e.type === 'usage')
    .map((e) => (e.payload as any).usage || {})
  const inT = usage.reduce((s, u: any) => s + (u.input_tokens || 0), 0)
  const outT = usage.reduce((s, u: any) => s + (u.output_tokens || 0), 0)
  return { input: inT, output: outT, total: inT + outT }
})

const costEstimate = computed(() => task.current?.cost_usd ?? 0)
const budget = computed(() => session.budgetUsd || 50)
const budgetUsedPct = computed(() => Math.min(100, (costEstimate.value / Math.max(0.01, budget.value)) * 100))

const citationSources = computed(() => {
  const total = task.finalReport?.citations?.length ?? 0
  if (!total) return { total: 0, items: [] as any[] }
  // Buckets by source_type rough approximation
  const bySite = new Map<string, number>()
  task.finalReport!.citations.forEach((c) => {
    try {
      const u = new URL(c.url)
      const host = u.hostname
      let bucket = '其他'
      if (host.includes('arxiv') || host.includes('scholar')) bucket = '学术论文'
      else if (host.includes('idc') || host.includes('gartner') || host.includes('mckinsey')) bucket = '行业报告'
      else if (host.includes('patent')) bucket = '专利'
      else bucket = '网页'
      bySite.set(bucket, (bySite.get(bucket) || 0) + 1)
    } catch { bySite.set('网页', (bySite.get('网页') || 0) + 1) }
  })
  const items = Array.from(bySite.entries()).map(([k, v]) => ({ label: k, value: v, pct: Math.round((v / total) * 100) }))
  return { total, items }
})

// Confidence distribution derived from findings.confidence
const confidence = computed(() => {
  const findings = task.findings
  if (!findings.length) return { high: 0, medium: 0, low: 0, total: 0 }
  let h = 0, m = 0, l = 0
  for (const f of findings) {
    if (f.confidence >= 0.8) h++
    else if (f.confidence >= 0.5) m++
    else l++
  }
  const total = h + m + l
  return {
    high:   Math.round((h / total) * 100),
    medium: Math.round((m / total) * 100),
    low:    Math.round((l / total) * 100),
    total,
  }
})

async function pauseTask() {
  if (!task.current?.id) return
  await task.stop()
  ElMessage.info('已请求暂停 (当前 MVP 实现为中断)')
}
async function abortTask() {
  if (!task.current?.id) return
  await task.stop()
  ElMessage.warning('已发送终止信号')
}
async function copyId() {
  if (!task.current?.id) return
  await navigator.clipboard.writeText(task.current.id)
  ElMessage.success('Task ID 已复制')
}

function agentIconColor(color: string) {
  return ({
    blue: '#2563eb', green: '#16a34a', purple: '#7c3aed', orange: '#f97316',
  } as Record<string, string>)[color] || '#2563eb'
}
function agentBgColor(color: string) {
  return ({
    blue: '#dbeafe', green: '#dcfce7', purple: '#ede9fe', orange: '#ffedd5',
  } as Record<string, string>)[color] || '#dbeafe'
}
</script>

<template>
  <div class="wb">
    <!-- ============= Header card ============= -->
    <section class="wb-head card">
      <div class="wb-head-left">
        <div class="wb-icon"><ElIcon><Document /></ElIcon></div>
        <div class="wb-meta">
          <h2>研究:{{ taskTitle }}</h2>
          <div class="wb-sub">
            <span>任务 ID: <code>{{ taskId }}</code></span>
            <ElIcon class="copy-icon" @click="copyId"><CopyDocument /></ElIcon>
          </div>
          <div class="wb-sub-row">
            <span><ElIcon><Reading /></ElIcon> 创建时间: {{ createdAt }}</span>
            <span><ElIcon><Reading /></ElIcon> 预计完成: {{ estimatedAt }}</span>
          </div>
        </div>
      </div>
      <div class="wb-head-mid">
        <div class="wb-prog-label">总体进度</div>
        <div class="wb-prog-value">{{ progress }}%</div>
        <div class="wb-prog-bar"><i :style="{ width: progress + '%' }" /></div>
        <div class="wb-prog-foot">进度更新: 2 分钟前</div>
      </div>
      <div class="wb-head-right">
        <button class="ghost-btn" @click="pauseTask">
          <ElIcon><VideoPause /></ElIcon> <span>暂停任务</span>
        </button>
        <button class="ghost-btn danger" @click="abortTask">
          <ElIcon><CircleClose /></ElIcon> <span>终止任务</span>
        </button>
      </div>
    </section>

    <!-- ============= Step bar ============= -->
    <section class="wb-steps card">
      <div class="wb-step" v-for="(step, i) in steps" :key="step.key" :data-state="stepState(i)">
        <div class="wb-step-circle">
          <template v-if="stepState(i) === 'done'">
            <ElIcon><Check /></ElIcon>
          </template>
          <template v-else-if="stepState(i) === 'current'">
            <span>{{ i + 1 }}</span>
          </template>
          <template v-else>
            <span>{{ i + 1 }}</span>
          </template>
        </div>
        <div class="wb-step-label">{{ step.label }}</div>
        <div v-if="i < steps.length - 1" class="wb-step-line" :class="{ done: stepState(i + 1) !== 'todo' || stepState(i) === 'done' }" />
      </div>
    </section>

    <!-- ============= 4-col grid ============= -->
    <section class="wb-grid">
      <!-- Col 1: Live SSE + Research plan -->
      <div class="wb-col">
        <article class="card">
          <header class="card-pad-tight section-head">
            <h3 class="card-title">实时活动 (Live SSE)</h3>
            <span class="badge-live"><i /> 实时</span>
          </header>
          <div class="live-list">
            <ElEmpty v-if="!liveEvents.length" :image-size="56" description="等待事件…" />
            <div v-for="(e, i) in liveEvents" :key="i" class="live-row" :data-type="e.type">
              <span class="live-time">{{ e.time }}</span>
              <span class="live-dot" :data-type="e.type" />
              <div class="live-body">
                <strong>{{ e.title }}</strong>
                <p>{{ e.detail }}</p>
              </div>
            </div>
          </div>
        </article>

        <article class="card">
          <header class="card-pad-tight section-head">
            <h3 class="card-title">研究计划 ({{ planSteps.filter(p => p.done).length }}/{{ planSteps.length }})</h3>
          </header>
          <ul class="plan-list">
            <li v-for="(p, i) in planSteps" :key="i" :class="{ done: p.done }">
              <span class="plan-check">
                <ElIcon v-if="p.done"><Check /></ElIcon>
                <span v-else>{{ i + 1 }}</span>
              </span>
              <span>{{ p.label }}</span>
            </li>
          </ul>
          <div class="link-foot">
            <span>查看研究计划详情</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>
      </div>

      <!-- Col 2: Parallel research hub -->
      <div class="wb-col">
        <article class="card">
          <header class="card-pad-tight section-head">
            <h3 class="card-title">并行研究 ({{ researcherAgents.filter(a => a.status === 'done').length }}/{{ researcherAgents.length }})</h3>
            <a class="link-mini">全部展开</a>
          </header>
          <div class="hub-wrap">
            <div class="hub-center">
              <div class="hub-glyph">
                <ElIcon :size="22"><Connection /></ElIcon>
              </div>
              <strong>Athena Research Hub</strong>
              <small>并行执行中</small>
            </div>
            <div class="hub-grid">
              <div v-for="a in researcherAgents" :key="a.name" class="hub-card" :data-color="a.color">
                <div class="hub-ico" :style="{ background: agentBgColor(a.color), color: agentIconColor(a.color) }">
                  <ElIcon><component :is="a.icon" /></ElIcon>
                </div>
                <div class="hub-name" :title="a.name">{{ a.name }}</div>
                <div class="hub-status" :class="a.status">
                  <span v-if="a.status === 'done'">已完成</span>
                  <span v-else-if="a.status === 'progress'">进行中 {{ a.progress }}%</span>
                  <span v-else>排队中</span>
                </div>
                <ul class="hub-meta">
                  <li>已检索 <b>{{ a.collected }}</b> 个来源</li>
                  <li>已处理 <b>{{ a.processed }}/{{ a.total }}</b> 查询</li>
                </ul>
                <div v-if="a.status === 'progress'" class="hub-bar"><i :style="{ width: a.progress + '%', background: agentIconColor(a.color) }" /></div>
              </div>
            </div>
          </div>
          <div class="link-foot">
            <span>查看并行研究详情</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>
      </div>

      <!-- Col 3: Report preview -->
      <div class="wb-col">
        <article class="card report-preview">
          <header class="card-pad-tight section-head">
            <h3 class="card-title">报告预览 (实时 Markdown)</h3>
            <span class="badge-live"><i /> 实时更新</span>
          </header>
          <div class="report-body" v-if="reportHtml" v-html="reportHtml" />
          <ElEmpty v-else :image-size="64" description="Writer 将在此处实时输出 Markdown" />
          <div class="link-foot" v-if="task.current">
            <span>在新标签页中查看完整报告</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>
      </div>

      <!-- Col 4: Right meta -->
      <div class="wb-col">
        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">引用来源 ({{ citationSources.total }})</h3>
          </header>
          <div class="donut-wrap">
            <svg viewBox="0 0 80 80" class="donut" aria-hidden="true">
              <circle cx="40" cy="40" r="32" fill="none" stroke="#e5e7eb" stroke-width="10" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#2563eb" stroke-width="10"
                      stroke-dasharray="201" :stroke-dashoffset="201 - (201 * Math.min(100, citationSources.total) / 100)"
                      transform="rotate(-90 40 40)" stroke-linecap="round" />
            </svg>
            <div class="donut-legend">
              <div v-for="(it, i) in citationSources.items" :key="i" class="legend-row">
                <span class="dot" :style="{ background: ['#2563eb','#16a34a','#f97316','#7c3aed'][i % 4] }" />
                <span class="legend-label">{{ it.label }}</span>
                <b>{{ it.value }}</b>
                <span class="legend-pct">({{ it.pct }}%)</span>
              </div>
            </div>
          </div>
          <div class="link-foot">
            <span>查看全部来源</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>

        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">置信度分布</h3>
          </header>
          <template v-if="confidence.total > 0">
            <div class="conf-bar">
              <span class="conf high"   :style="{ width: confidence.high + '%' }" />
              <span class="conf medium" :style="{ width: confidence.medium + '%' }" />
              <span class="conf low"    :style="{ width: confidence.low + '%' }" />
            </div>
            <div class="conf-legend">
              <span><i class="bg-high" /> 高 {{ confidence.high }}%</span>
              <span><i class="bg-medium" /> 中 {{ confidence.medium }}%</span>
              <span><i class="bg-low" /> 低 {{ confidence.low }}%</span>
            </div>
            <p class="muted-line">基于 {{ confidence.total }} 个 findings 的 confidence 字段</p>
          </template>
          <ElEmpty v-else :image-size="48" description="等待 Researcher 结果" />
        </article>

        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">成本估算</h3>
          </header>
          <div class="cost-value">
            <span class="big">$ {{ costEstimate.toFixed(2) }}</span>
            <span class="unit">USD</span>
          </div>
          <div class="kv-line"><span>预算</span><b>${{ budget.toFixed(2) }} ({{ budgetUsedPct.toFixed(0) }}%)</b></div>
          <div class="rp-bar"><i :style="{ width: budgetUsedPct + '%' }" /></div>
          <div class="link-foot">
            <span>查看成本明细</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>

        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">Token 使用</h3>
          </header>
          <div class="token-summary">
            <span class="big">{{ (tokenUsed.total / 1e6).toFixed(2) }}M</span>
            <span class="unit">/ 10.00M</span>
          </div>
          <div class="kv-line"><span>输入</span><b>{{ (tokenUsed.input / 1e6).toFixed(2) }}M</b></div>
          <div class="kv-line"><span>输出</span><b>{{ (tokenUsed.output / 1e6).toFixed(2) }}M</b></div>
          <div class="link-foot">
            <span>查看使用详情</span>
            <ElIcon><ArrowRight /></ElIcon>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.wb { display: grid; gap: 16px; }

/* Head */
.wb-head { padding: 18px 22px; display: grid; grid-template-columns: 1.5fr 1fr 220px; gap: 18px; align-items: center; }
.wb-head-left { display: flex; gap: 14px; align-items: flex-start; }
.wb-icon { width: 44px; height: 44px; border-radius: 10px; background: #dbeafe; color: #2563eb; display: grid; place-items: center; flex-shrink: 0; }
.wb-icon .el-icon { font-size: 18px; }
.wb-meta h2 { margin: 0 0 6px; font-size: 18px; font-weight: 700; color: var(--text); letter-spacing: -.01em; }
.wb-sub, .wb-sub-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--muted); }
.wb-sub-row { gap: 16px; margin-top: 4px; }
.wb-sub-row .el-icon { font-size: 12px; }
.wb-sub code { font-family: var(--t-mono); font-size: 12px; color: var(--text-soft); }
.copy-icon { cursor: pointer; color: var(--muted-soft); font-size: 13px; transition: color .12s ease; }
.copy-icon:hover { color: var(--primary); }

.wb-head-mid { display: grid; gap: 4px; }
.wb-prog-label { font-size: 12.5px; color: var(--muted); }
.wb-prog-value { font-size: 28px; font-weight: 700; color: var(--primary); letter-spacing: -.015em; line-height: 1.1; }
.wb-prog-bar { height: 6px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.wb-prog-bar i { display: block; height: 100%; background: var(--primary); transition: width .3s ease; }
.wb-prog-foot { font-size: 11.5px; color: var(--muted); }

.wb-head-right { display: grid; gap: 8px; }
.ghost-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 38px;
  padding: 0 14px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-soft);
  font: inherit;
  cursor: pointer;
  font-weight: 500;
  font-size: 13px;
  transition: all .12s ease;
}
.ghost-btn:hover { border-color: var(--primary-line); color: var(--primary); }
.ghost-btn.danger { color: var(--red); }
.ghost-btn.danger:hover { border-color: var(--red); background: var(--red-soft); }

/* Steps */
.wb-steps {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  align-items: center;
  padding: 22px 22px 18px;
  position: relative;
}
.wb-step { position: relative; display: grid; place-items: center; gap: 10px; }
.wb-step-circle {
  width: 38px; height: 38px;
  display: grid; place-items: center;
  border-radius: 50%;
  background: var(--surface);
  border: 2px solid var(--border-strong);
  color: var(--muted);
  font-weight: 700; font-size: 13px;
  font-family: var(--t-mono);
  position: relative;
  z-index: 1;
}
.wb-step[data-state='done'] .wb-step-circle {
  background: var(--primary-soft);
  border-color: var(--primary);
  color: var(--primary);
}
.wb-step[data-state='current'] .wb-step-circle {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  box-shadow: 0 0 0 4px var(--primary-soft);
}
.wb-step-label { font-size: 12.5px; font-weight: 500; color: var(--muted); text-align: center; }
.wb-step[data-state='current'] .wb-step-label { color: var(--primary); font-weight: 600; }
.wb-step[data-state='done'] .wb-step-label { color: var(--text-soft); }
.wb-step-line {
  position: absolute;
  top: 19px;
  left: calc(50% + 22px);
  width: calc(100% - 38px);
  height: 2px;
  background: var(--border-strong);
  z-index: 0;
}
.wb-step[data-state='done'] + .wb-step .wb-step-line,
.wb-step-line.done { background: var(--primary); }
.wb-step:last-child .wb-step-line { display: none; }

/* Grid */
.wb-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1.3fr) minmax(0, .9fr);
  gap: 16px;
  align-items: start;
}
.wb-col { display: grid; gap: 16px; min-width: 0; }

.section-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}
.card-pad-tight { padding: 16px 18px 0; }
.card-pad-tight + .live-list, .card-pad-tight + .plan-list, .card-pad-tight + .hub-wrap, .card-pad-tight + .report-body { padding: 0 18px 6px; }
.card .link-foot {
  display: flex; align-items: center; justify-content: center;
  gap: 6px;
  padding: 12px 18px;
  font-size: 12.5px;
  color: var(--muted);
  cursor: pointer;
  border-top: 1px solid var(--border);
  margin-top: 8px;
  transition: color .12s ease;
}
.card .link-foot:hover { color: var(--primary); }
.link-mini { font-size: 12px; color: var(--primary); cursor: pointer; }

.badge-live {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--green-soft);
  color: var(--green-text);
  font-size: 11px;
  font-weight: 600;
}
.badge-live i {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--green);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: .6; } 50% { opacity: 1; } }

/* Live list */
.live-list { display: grid; gap: 10px; }
.live-row {
  display: grid;
  grid-template-columns: 60px 8px 1fr;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
}
.live-time { font-family: var(--t-mono); font-size: 11.5px; color: var(--muted-soft); padding-top: 3px; }
.live-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--primary);
  margin-top: 6px;
}
.live-dot[data-type='quality'] { background: var(--orange); }
.live-dot[data-type='finding'] { background: var(--green); }
.live-dot[data-type='route']   { background: var(--purple); }
.live-dot[data-type='done']    { background: var(--green); }
.live-dot[data-type='error']   { background: var(--red); }
.live-body strong { font-size: 13px; font-weight: 600; color: var(--text); display: block; }
.live-body p { margin: 2px 0 0; color: var(--muted); font-size: 12.5px; line-height: 1.5; }

/* Plan list */
.plan-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.plan-list li {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px;
  color: var(--muted);
}
.plan-list li.done { color: var(--text); }
.plan-check {
  width: 20px; height: 20px;
  border-radius: 50%;
  background: var(--surface-3);
  color: var(--muted);
  display: grid; place-items: center;
  font-size: 11px;
  font-family: var(--t-mono);
  flex-shrink: 0;
}
.plan-list li.done .plan-check {
  background: var(--green-soft);
  color: var(--green);
}
.plan-list li.done .plan-check .el-icon { font-size: 12px; font-weight: 700; }

/* Hub */
.hub-wrap { position: relative; padding: 6px 6px 0; }
.hub-center {
  display: grid; place-items: center;
  gap: 4px;
  padding: 14px 0 16px;
}
.hub-glyph {
  width: 60px; height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #dbeafe, #ede9fe);
  display: grid; place-items: center;
  color: var(--primary);
  margin-bottom: 4px;
  border: 2px dashed #bfdbfe;
}
.hub-center strong { font-size: 13px; font-weight: 700; color: var(--text); }
.hub-center small { font-size: 11px; color: var(--muted); }
.hub-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.hub-card {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}
.hub-ico {
  width: 30px; height: 30px;
  display: grid; place-items: center;
  border-radius: 8px;
  margin-bottom: 6px;
}
.hub-ico .el-icon { font-size: 14px; }
.hub-name { font-size: 13px; font-weight: 600; color: var(--text); }
.hub-status { font-size: 11px; font-weight: 600; margin-top: 2px; color: var(--primary); }
.hub-status.queued { color: var(--orange); }
.hub-meta { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 4px; }
.hub-meta li { font-size: 11.5px; color: var(--muted); }
.hub-meta li b { color: var(--text); font-weight: 600; }
.hub-meta li.muted { color: var(--muted-soft); }
.hub-bar { margin-top: 8px; height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.hub-bar i { display: block; height: 100%; border-radius: inherit; }

/* Report preview */
.report-preview {
  display: flex; flex-direction: column; min-height: 100%;
  min-width: 0;      /* allow the flex/grid child to shrink */
  overflow: hidden;  /* clip long URLs / code that overflow horizontally */
}
.report-body {
  padding: 4px 18px 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-soft);
  max-height: 480px;
  overflow: auto;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.report-body :deep(*) {
  max-width: 100%;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.report-body :deep(pre) { white-space: pre-wrap; overflow-x: auto; }
.report-body :deep(a) { word-break: break-all; }
.report-body :deep(h1) { font-size: 16px; margin: 0 0 10px; font-weight: 700; }
.report-body :deep(h2) { font-size: 14px; margin: 14px 0 6px; color: var(--primary); }
.report-body :deep(h3) { font-size: 13px; margin: 10px 0 4px; }
.report-body :deep(p), .report-body :deep(li) { margin: 4px 0; }
.report-body :deep(code) {
  font-family: var(--t-mono); font-size: 11.5px;
  background: var(--primary-soft); color: var(--primary);
  padding: 1px 5px; border-radius: 4px;
  word-break: break-all;
}

/* Donut */
.donut-wrap { display: flex; gap: 12px; align-items: center; }
.donut { width: 80px; height: 80px; flex-shrink: 0; }
.donut-legend { display: grid; gap: 6px; flex: 1; font-size: 12px; }
.legend-row { display: flex; align-items: center; gap: 6px; }
.legend-row .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.legend-row .legend-label { flex: 1; color: var(--text-soft); }
.legend-row b { color: var(--text); font-weight: 600; }
.legend-row .legend-pct { color: var(--muted-soft); font-size: 11px; }

/* Confidence */
.conf-bar {
  display: flex;
  height: 14px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-3);
  margin-bottom: 10px;
}
.conf { display: block; height: 100%; }
.conf.high   { background: var(--green); }
.conf.medium { background: var(--yellow); }
.conf.low    { background: var(--red); }
.conf-legend { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--muted); }
.conf-legend i {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.conf-legend i.bg-high   { background: var(--green); }
.conf-legend i.bg-medium { background: var(--yellow); }
.conf-legend i.bg-low    { background: var(--red); }
.muted-line { color: var(--muted-soft); font-size: 11px; margin: 8px 0 0; }

/* Cost / token */
.cost-value, .token-summary { display: flex; align-items: baseline; gap: 6px; margin: 4px 0 10px; }
.big { font-size: 24px; font-weight: 700; color: var(--text); letter-spacing: -.015em; }
.unit { font-size: 12px; color: var(--muted); font-family: var(--t-mono); }
.kv-line { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); padding: 4px 0; }
.kv-line b { color: var(--text-soft); font-weight: 600; }
.rp-bar { height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.rp-bar i { display: block; height: 100%; background: var(--primary); }

@media (max-width: 1700px) {
  .wb-grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  }
  /* Report preview takes its own row so long text doesn't bleed into other panels */
  .wb-col:nth-child(3) { grid-column: 1 / -1; }
  /* Meta column also full-width but its children lay out in 4 boxes side-by-side */
  .wb-col:nth-child(4) {
    grid-column: 1 / -1;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    grid-auto-rows: 1fr;
  }
}
@media (max-width: 900px) {
  .wb-grid { grid-template-columns: 1fr; }
  .wb-col { grid-column: auto !important; grid-template-columns: 1fr !important; }
  .wb-head { grid-template-columns: 1fr; }
  .wb-steps { grid-template-columns: repeat(4, 1fr); gap: 16px; }
}
</style>
