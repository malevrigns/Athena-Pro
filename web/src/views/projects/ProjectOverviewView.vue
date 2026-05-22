<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Connection,
  DataAnalysis,
  Document,
  Files,
  Finished,
  Grid,
  Link,
  Notebook,
  Operation,
  TrendCharts,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores/projects'
import { useEntrance } from '@/composables/useAnime'
import type { ProjectStatus } from '@/types/research'

const props = defineProps<{ id: string }>()
const router = useRouter()
const store = useProjectStore()

useEntrance('.console-head, .pipeline-step, .asset-tile, .next-action, .context-band > div', { delay: (_el, i) => 70 + i * 55 })

onMounted(() => load())
watch(() => props.id, () => load())

const project = computed(() => store.current)
const constraints = computed(() => project.value?.constraints ?? [])
const traceCount = computed(() => store.trace.length)

const operatingStages = computed(() => [
  workflowStage('literature', '文献调研', Document, store.papers.length, '/literature'),
  workflowStage('paper_notes', '结构化阅读', Notebook, noteCount.value, '/literature'),
  workflowStage('evidence', '证据抽取', Link, 0),
  workflowStage('taxonomy', '技术谱系', Grid, 0),
  workflowStage('baseline', 'Baseline', TrendCharts, 0),
  workflowStage('idea', 'Idea', Connection, 0),
  workflowStage('experiment', '实验框架', DataAnalysis, 0),
])

const noteCount = computed(() =>
  Object.values(store.paperNotes).reduce((total, notes) => total + notes.length, 0),
)

const assetTiles = computed(() => [
  { label: 'Papers', value: store.papers.length, hint: '论文库', tone: 'blue' },
  { label: 'PaperNotes', value: noteCount.value, hint: '已结构化阅读', tone: 'green' },
  { label: 'Tool Trace', value: traceCount.value, hint: '工具调用记录', tone: 'violet' },
  { label: 'Reviews', value: project.value?.status === 'waiting_review' ? 1 : 0, hint: '阻塞审批点', tone: 'amber' },
])

const nextActions = computed(() => [
  {
    key: 'literature',
    title: store.papers.length ? '继续筛选与阅读论文' : '先建立论文库',
    body: store.papers.length ? '进入 Literature，选择论文并生成 PaperNote。' : '用 paper_search 收集候选论文，再开始结构化阅读。',
    icon: Document,
    enabled: true,
    target: `/projects/${props.id}/literature`,
  },
  {
    key: 'trace',
    title: '检查工具执行证据',
    body: '查看 paper_search / paper_reader 的调用、参数和 observation。',
    icon: Finished,
    enabled: traceCount.value > 0,
    target: `/projects/${props.id}/trace`,
  },
  {
    key: 'baseline',
    title: '等待 Baseline 地基',
    body: '下一阶段接入 baseline 候选、评分和人工阻塞选择。',
    icon: Operation,
    enabled: false,
    target: '',
  },
])

function workflowStage(
  key: string,
  label: string,
  icon: any,
  count: number,
  routeSuffix = '',
) {
  return {
    key,
    label,
    icon,
    count,
    state: count > 0 ? 'active' : routeSuffix ? 'ready' : 'locked',
    route: routeSuffix ? `/projects/${props.id}${routeSuffix}` : '',
  }
}

function statusMeta(status?: ProjectStatus) {
  const map: Record<ProjectStatus, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
    draft: { label: '草稿', type: 'info' },
    planning: { label: '规划中', type: 'primary' },
    running: { label: '运行中', type: 'primary' },
    waiting_review: { label: '待审批', type: 'warning' },
    completed: { label: '已完成', type: 'success' },
    failed: { label: '失败', type: 'danger' },
    cancelled: { label: '已取消', type: 'info' },
  }
  return status ? map[status] : map.draft
}

function fmtDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

async function load() {
  try {
    await Promise.all([
      store.loadProject(props.id),
      store.loadPapers(props.id),
      store.loadTrace(props.id),
    ])
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

function openRoute(target: string) {
  if (!target) return
  router.push(target)
}
</script>

<template>
  <div class="research-console">
    <section class="console-head">
      <button class="back-btn" @click="router.push('/projects')">
        <ElIcon><ArrowLeft /></ElIcon>
      </button>
      <div class="console-title">
        <div class="head-kicker">Research OS Console</div>
        <h2>{{ project?.title || '—' }}</h2>
        <p>{{ project?.research_question || '—' }}</p>
      </div>
      <div class="console-actions">
        <ElTag :type="statusMeta(project?.status).type">{{ statusMeta(project?.status).label }}</ElTag>
        <button class="primary-btn" @click="router.push(`/projects/${props.id}/literature`)">
          <ElIcon><Document /></ElIcon>
          <span>进入文献库</span>
        </button>
      </div>
    </section>

    <section class="context-band">
      <div>
        <span>Field</span>
        <strong>{{ project?.field || '未设置' }}</strong>
      </div>
      <div>
        <span>Venue</span>
        <strong>{{ project?.target_venue || '未设置' }}</strong>
      </div>
      <div>
        <span>Updated</span>
        <strong>{{ fmtDate(project?.updated_at) }}</strong>
      </div>
      <div>
        <span>Owner</span>
        <strong>{{ project?.owner || '—' }}</strong>
      </div>
    </section>

    <section class="pipeline-strip" aria-label="Research workflow">
      <button
        v-for="stage in operatingStages"
        :key="stage.key"
        class="pipeline-step"
        :data-state="stage.state"
        :disabled="!stage.route"
        @click="openRoute(stage.route)"
      >
        <span class="step-icon"><ElIcon><component :is="stage.icon" /></ElIcon></span>
        <span class="step-copy">
          <strong>{{ stage.label }}</strong>
          <small>{{ stage.state === 'active' ? `${stage.count} assets` : stage.state === 'ready' ? '可进入' : '待接入' }}</small>
        </span>
      </button>
    </section>

    <section class="console-grid">
      <div class="asset-board">
        <header>
          <div>
            <div class="head-kicker">Workspace Assets</div>
            <h3>研究资产面板</h3>
          </div>
          <button class="ghost-btn" @click="router.push(`/projects/${props.id}/trace`)">
            <ElIcon><Finished /></ElIcon>
            <span>Trace</span>
          </button>
        </header>
        <div class="asset-grid">
          <article v-for="tile in assetTiles" :key="tile.label" class="asset-tile" :data-tone="tile.tone">
            <span>{{ tile.label }}</span>
            <strong>{{ tile.value }}</strong>
            <small>{{ tile.hint }}</small>
          </article>
        </div>
      </div>

      <aside class="next-panel">
        <header>
          <div class="head-kicker">Next Actions</div>
          <h3>下一步</h3>
        </header>
        <button
          v-for="action in nextActions"
          :key="action.key"
          class="next-action"
          :disabled="!action.enabled"
          @click="openRoute(action.target)"
        >
          <span class="action-icon"><ElIcon><component :is="action.icon" /></ElIcon></span>
          <span>
            <strong>{{ action.title }}</strong>
            <small>{{ action.body }}</small>
          </span>
        </button>
      </aside>
    </section>

    <section class="constraint-row">
      <div class="head-kicker">Constraints</div>
      <div v-if="constraints.length" class="constraint-list">
        <span v-for="item in constraints" :key="item" class="constraint-chip">{{ item }}</span>
      </div>
      <span v-else class="empty-constraint">暂无约束</span>
    </section>
  </div>
</template>

<style scoped>
.research-console {
  display: grid;
  gap: 16px;
}
.console-head {
  min-height: 170px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--surface) 88%, #dbeafe) 0%, var(--surface) 48%, color-mix(in srgb, var(--surface) 88%, #ecfeff) 100%);
  padding: 24px;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
}
.back-btn,
.ghost-btn {
  height: 38px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}
.back-btn {
  width: 40px;
  display: grid;
  place-items: center;
}
.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
}
.back-btn:hover,
.ghost-btn:hover {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: var(--primary-line);
}
.head-kicker {
  color: var(--primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.console-title h2 {
  margin: 5px 0 8px;
  font-size: 28px;
  line-height: 1.15;
}
.console-title p {
  max-width: 960px;
  margin: 0;
  color: var(--text-soft);
  line-height: 1.6;
}
.console-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.context-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.context-band > div {
  min-height: 72px;
  padding: 14px 16px;
  display: grid;
  align-content: center;
  gap: 4px;
  border-right: 1px solid var(--border);
}
.context-band > div:last-child { border-right: 0; }
.context-band span,
.asset-tile span,
.asset-tile small,
.pipeline-step small,
.next-action small {
  color: var(--muted);
  font-size: 12px;
}
.context-band strong {
  overflow-wrap: anywhere;
}
.pipeline-strip {
  display: grid;
  grid-template-columns: repeat(7, minmax(112px, 1fr));
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.pipeline-step {
  min-height: 88px;
  min-width: 112px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  padding: 12px;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}
.pipeline-step:disabled {
  cursor: default;
  opacity: .62;
}
.pipeline-step[data-state="active"] {
  border-color: #86efac;
  background: color-mix(in srgb, var(--green-soft) 44%, var(--surface));
}
.pipeline-step[data-state="ready"] {
  border-color: var(--primary-line);
}
.step-icon,
.action-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--surface-3);
  color: var(--primary);
}
.step-copy {
  min-width: 0;
  display: grid;
  gap: 4px;
}
.step-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.console-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
  gap: 16px;
  align-items: start;
}
.asset-board,
.next-panel,
.constraint-row {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 18px;
}
.asset-board header,
.next-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.asset-board h3,
.next-panel h3 {
  margin: 3px 0 0;
  font-size: 16px;
}
.asset-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.asset-tile {
  min-height: 128px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  display: grid;
  align-content: space-between;
  background: var(--surface-2);
}
.asset-tile strong {
  font-family: var(--t-mono);
  font-size: 34px;
  line-height: 1;
}
.asset-tile[data-tone="green"] { border-color: #bbf7d0; background: color-mix(in srgb, var(--green-soft) 54%, var(--surface)); }
.asset-tile[data-tone="violet"] { border-color: #ddd6fe; background: color-mix(in srgb, #f5f3ff 68%, var(--surface)); }
.asset-tile[data-tone="amber"] { border-color: #fed7aa; background: color-mix(in srgb, #fff7ed 72%, var(--surface)); }
.next-panel {
  display: grid;
  gap: 10px;
}
.next-action {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  padding: 12px;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  text-align: left;
  cursor: pointer;
}
.next-action:disabled {
  cursor: default;
  opacity: .62;
}
.next-action:not(:disabled):hover {
  border-color: var(--primary-line);
  background: var(--primary-soft);
}
.next-action span:last-child {
  display: grid;
  gap: 4px;
}
.constraint-row {
  display: grid;
  gap: 10px;
}
.constraint-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.constraint-chip {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0 10px;
  background: var(--surface-2);
  color: var(--text-soft);
  font-size: 12px;
}
.empty-constraint {
  color: var(--muted);
}
@media (max-width: 1180px) {
  .console-grid,
  .context-band,
  .asset-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .context-band > div:nth-child(2) { border-right: 0; }
  .context-band > div:nth-child(-n+2) { border-bottom: 1px solid var(--border); }
}
@media (max-width: 760px) {
  .console-head,
  .console-grid,
  .context-band,
  .asset-grid { grid-template-columns: 1fr; }
  .console-actions { justify-content: flex-start; }
  .context-band > div { border-right: 0; border-bottom: 1px solid var(--border); }
  .context-band > div:last-child { border-bottom: 0; }
}
</style>
