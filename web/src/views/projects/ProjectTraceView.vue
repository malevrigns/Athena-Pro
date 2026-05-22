<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores/projects'
import { useEntrance } from '@/composables/useAnime'
import type { ToolTraceItem } from '@/types/research'

const props = defineProps<{ id: string }>()
const router = useRouter()
const store = useProjectStore()

useEntrance('.trace-head, .trace-stats > div, .trace-panel', { delay: (_el, i) => 80 + i * 70 })
useEntrance('.trace-item', { delay: (_el, i) => 240 + i * 45 })

onMounted(() => load())
watch(() => props.id, () => load())

const trace = computed(() => store.trace)
const failedCount = computed(() => trace.value.filter((item) => item.call.status === 'failed').length)
const approvalCount = computed(() =>
  trace.value.filter((item) => item.call.approval_status !== 'not_required').length,
)

async function load() {
  try {
    await Promise.all([store.loadProject(props.id), store.loadTrace(props.id)])
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

function fmtDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function statusType(status: string) {
  if (status === 'completed' || status === 'ok') return 'success'
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'waiting_approval') return 'warning'
  return 'info'
}

function compactJson(value: Record<string, unknown>) {
  const text = JSON.stringify(value)
  if (text.length <= 140) return text
  return `${text.slice(0, 137)}...`
}

function observationSummary(item: ToolTraceItem) {
  if (!item.observations.length) return '—'
  return item.observations.map((observation) => observation.summary).join(' / ')
}
</script>

<template>
  <div class="project-trace">
    <section class="trace-head">
      <button class="back-btn" @click="router.push(`/projects/${props.id}`)">
        <ElIcon><ArrowLeft /></ElIcon>
      </button>
      <div>
        <div class="head-kicker">Tool Trace</div>
        <h2>{{ store.current?.title || props.id }}</h2>
        <p class="mono">{{ props.id }}</p>
      </div>
      <button class="icon-action" aria-label="刷新" @click="load">
        <ElIcon><Refresh /></ElIcon>
      </button>
    </section>

    <section class="trace-stats">
      <div><span>调用</span><strong>{{ trace.length }}</strong></div>
      <div><span>审批</span><strong>{{ approvalCount }}</strong></div>
      <div><span>失败</span><strong>{{ failedCount }}</strong></div>
    </section>

    <section class="card trace-panel">
      <div v-if="trace.length" class="trace-list">
        <article v-for="item in trace" :key="item.call.id" class="trace-item">
          <div class="trace-dot" :data-status="item.call.status" />
          <div class="trace-main">
            <header>
              <div>
                <h3>{{ item.call.tool_name }}</h3>
                <p class="mono">{{ item.call.id }} · {{ fmtDate(item.call.created_at) }}</p>
              </div>
              <div class="trace-tags">
                <ElTag :type="statusType(item.call.status)">{{ item.call.status }}</ElTag>
                <ElTag effect="plain">{{ item.call.permission_level }}</ElTag>
              </div>
            </header>
            <div class="trace-args mono">{{ compactJson(item.call.arguments) }}</div>
            <div class="trace-observation">
              <span>Observation</span>
              <strong>{{ observationSummary(item) }}</strong>
            </div>
            <div v-if="item.observations.some((observation) => observation.error)" class="trace-error">
              <ElIcon><WarningFilled /></ElIcon>
              <span>{{ item.observations.find((observation) => observation.error)?.error }}</span>
            </div>
          </div>
        </article>
      </div>
      <ElEmpty v-else description="暂无工具调用" :image-size="92" />
    </section>
  </div>
</template>

<style scoped>
.project-trace { display: grid; gap: 18px; }
.trace-head {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 18px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 38px;
  gap: 16px;
  align-items: center;
}
.back-btn,
.icon-action {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}
.back-btn:hover,
.icon-action:hover {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: var(--primary-line);
}
.head-kicker {
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.trace-head h2 {
  margin: 3px 0;
  font-size: 22px;
}
.trace-head p { margin: 0; color: var(--muted); }
.trace-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.trace-stats > div {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 14px 16px;
  display: grid;
  gap: 4px;
}
.trace-stats span { color: var(--muted); font-size: 12px; }
.trace-stats strong { font-size: 24px; line-height: 1; }
.trace-panel { padding: 18px; }
.trace-list { display: grid; gap: 14px; }
.trace-item {
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  gap: 14px;
}
.trace-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 18px;
  background: var(--gray);
  box-shadow: 0 0 0 4px var(--gray-soft);
}
.trace-dot[data-status="completed"] { background: var(--green); box-shadow: 0 0 0 4px var(--green-soft); }
.trace-dot[data-status="failed"] { background: var(--red); box-shadow: 0 0 0 4px var(--red-soft); }
.trace-dot[data-status="waiting_approval"] { background: var(--yellow); box-shadow: 0 0 0 4px var(--yellow-soft); }
.trace-main {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  display: grid;
  gap: 12px;
}
.trace-main header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.trace-main h3 {
  margin: 0;
  font-size: 15px;
}
.trace-main p { margin: 3px 0 0; color: var(--muted); }
.trace-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.trace-args {
  min-height: 34px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text-soft);
  overflow-wrap: anywhere;
}
.trace-observation {
  display: grid;
  gap: 3px;
}
.trace-observation span {
  color: var(--muted);
  font-size: 12px;
}
.trace-observation strong {
  font-weight: 600;
  overflow-wrap: anywhere;
}
.trace-error {
  display: flex;
  gap: 8px;
  color: var(--red-text);
  background: var(--red-soft);
  border-radius: 8px;
  padding: 8px 10px;
}
@media (max-width: 760px) {
  .trace-stats { grid-template-columns: 1fr; }
  .trace-main header { flex-direction: column; }
  .trace-tags { justify-content: flex-start; }
}
</style>
