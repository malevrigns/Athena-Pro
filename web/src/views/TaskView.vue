<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, CopyDocument, Download, CircleClose,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import ReportRenderer from '@/components/report/ReportRenderer.vue'
import FindingBoard from '@/components/task/FindingBoard.vue'
import TaskTimeline from '@/components/task/TaskTimeline.vue'
import ResearchPlanMatrix from '@/components/task/ResearchPlanMatrix.vue'
import QualityGatePanel from '@/components/task/QualityGatePanel.vue'
import WorkflowCanvas from '@/components/task/WorkflowCanvas.vue'
import CitationsPanel from '@/components/report/CitationsPanel.vue'
import SourceInspector from '@/components/report/SourceInspector.vue'
import NodeCostBreakdown from '@/components/cost/NodeCostBreakdown.vue'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.task-head, .prog-strip', { delay: (_el, i) => 60 + i * 80 })
useEntrance('.task-left > *, .task-right', { delay: (_el, i) => 220 + i * 80 })

const props = defineProps<{ id: string }>()
const task = useTaskStore()
const session = useSessionStore()
const router = useRouter()
const tab = ref<'timeline' | 'plan' | 'quality' | 'sources' | 'graph' | 'cost'>('timeline')
const showFindings = ref(true)
const downloading = ref<string | null>(null)

onMounted(() => task.load(props.id))
watch(() => props.id, (id) => task.load(id))
onBeforeUnmount(() => task.closeStream())

const formats = computed(() => session.config?.export_formats || { md: true, html: true, pdf: false, docx: false })
const statusType = computed(() => {
  const s = task.status
  if (s === 'done') return 'success'
  if (s === 'failed' || s === 'cancelled') return 'danger'
  return 'primary'
})

async function download(fmt: 'md' | 'html' | 'pdf' | 'docx') {
  if (!task.current?.id) return
  if ((fmt === 'pdf' || fmt === 'docx') && !formats.value[fmt]) {
    ElMessage.warning(`${fmt.toUpperCase()} 服务端未启用`)
    return
  }
  downloading.value = fmt
  try { await task.downloadReport(fmt); ElMessage.success(`已下载 ${fmt.toUpperCase()}`) }
  catch (e) { ElMessage.error((e as Error).message) }
  finally { downloading.value = null }
}

async function copy() {
  const md = task.finalReport?.markdown || task.writerStream
  if (!md) return
  await navigator.clipboard.writeText(md)
  ElMessage.success('Markdown 已复制')
}

const iteration = computed(() => (task.supervisorIterations[task.supervisorIterations.length - 1]?.iteration) ?? 1)
</script>

<template>
  <div class="task-page">
    <!-- Sub head -->
    <div class="task-head">
      <div class="task-head-left">
        <ElButton size="small" :icon="ArrowLeft" link @click="router.push('/history')">历史</ElButton>
        <h2 :title="task.current?.question">{{ task.current?.question || '加载中…' }}</h2>
      </div>
      <div class="task-head-right">
        <ElTag :type="statusType" round size="small">{{ task.status }}</ElTag>
        <span class="task-meta">
          <code>{{ task.current?.id }}</code>
        </span>
        <ElDivider direction="vertical" />
        <ElButton size="small" :icon="CopyDocument" :disabled="!task.finalReport && !task.writerStream" @click="copy">复制</ElButton>
        <ElDropdown trigger="click">
          <ElButton size="small" :icon="Download" type="primary">下载</ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem :disabled="!task.finalReport" @click="download('md')">Markdown (.md)</ElDropdownItem>
              <ElDropdownItem :disabled="!task.finalReport" @click="download('html')">HTML (.html)</ElDropdownItem>
              <ElDropdownItem :disabled="!task.finalReport || !formats.pdf" @click="download('pdf')">PDF (.pdf)</ElDropdownItem>
              <ElDropdownItem :disabled="!task.finalReport || !formats.docx" @click="download('docx')">DOCX (.docx)</ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
        <ElButton
          v-if="task.isRunning"
          size="small"
          type="danger"
          plain
          :icon="CircleClose"
          @click="task.stop()"
        >中断</ElButton>
      </div>
    </div>

    <!-- Progress strip -->
    <div class="prog-strip">
      <ElProgress :percentage="task.progress" :stroke-width="3" :show-text="false" :status="statusType === 'success' ? 'success' : statusType === 'danger' ? 'exception' : undefined" />
      <div class="prog-info">
        <span>进度 {{ task.progress }}%</span>
        <span class="dot" />
        <span>迭代轮 {{ iteration }}</span>
        <span class="dot" />
        <span>{{ task.findings.length }} findings</span>
        <span class="dot" />
        <span>引用 {{ task.finalReport?.citations.length || 0 }}</span>
        <span class="dot" />
        <span>成本 ${{ (task.current?.cost_usd || 0).toFixed(5) }}</span>
        <span class="dot" />
        <span>质量 {{ (task.quality?.overall || 0).toFixed(2) }}</span>
      </div>
    </div>

    <!-- Main 2-col -->
    <div class="task-grid">
      <!-- Left: report + findings -->
      <div class="task-left">
        <ReportRenderer :report="task.finalReport" :stream="task.writerStream" />
        <div v-if="task.findings.length" class="findings-wrap">
          <div class="findings-head">
            <span>研究发现 ({{ task.findings.length }})</span>
            <ElButton link type="primary" size="small" @click="showFindings = !showFindings">
              {{ showFindings ? '隐藏 ▾' : '展开 ▸' }}
            </ElButton>
          </div>
          <FindingBoard v-if="showFindings" :findings="task.findings" />
        </div>
      </div>

      <!-- Right: drawer with tabs -->
      <aside class="task-right">
        <div class="tabs">
          <button :class="{ active: tab === 'timeline' }" @click="tab = 'timeline'">事件流</button>
          <button :class="{ active: tab === 'plan' }" @click="tab = 'plan'">计划</button>
          <button :class="{ active: tab === 'quality' }" @click="tab = 'quality'">质量</button>
          <button :class="{ active: tab === 'sources' }" @click="tab = 'sources'">引用</button>
          <button :class="{ active: tab === 'graph' }" @click="tab = 'graph'">图</button>
          <button :class="{ active: tab === 'cost' }" @click="tab = 'cost'">成本</button>
        </div>
        <div class="tab-body">
          <TaskTimeline v-if="tab === 'timeline'" :events="task.events" />
          <ResearchPlanMatrix v-else-if="tab === 'plan'" :plan="task.plan" />
          <QualityGatePanel v-else-if="tab === 'quality'" :quality="task.quality" />
          <div v-else-if="tab === 'sources'" class="stack">
            <CitationsPanel :report="task.finalReport" />
            <SourceInspector />
          </div>
          <WorkflowCanvas
            v-else-if="tab === 'graph'"
            :status="task.status"
            :progress="task.progress"
            :findings="task.findings.length"
            :iteration="iteration"
          />
          <NodeCostBreakdown v-else-if="tab === 'cost'" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.task-page { display: grid; gap: 16px; min-width: 0; }

.task-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 16px; flex-wrap: wrap;
}
.task-head-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
.task-head-left h2 {
  margin: 0;
  font-size: var(--t-22);
  font-weight: 600;
  letter-spacing: -.015em;
  color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 640px;
}
.task-head-right { display: flex; align-items: center; gap: 10px; }
.task-meta code { font-family: var(--t-mono); font-size: 11px; color: var(--muted); }

.prog-strip {
  display: flex; flex-direction: column; gap: 8px;
  padding: 0;
}
.prog-info {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: var(--muted);
}
.prog-info .dot { width: 3px; height: 3px; border-radius: 50%; background: var(--muted-soft); }

.task-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 18px;
  align-items: flex-start;
}

.task-left { display: grid; gap: 16px; min-width: 0; }
.findings-wrap { display: grid; gap: 8px; }
.findings-head {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; color: var(--muted-soft);
  padding: 0 4px;
}

.task-right {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-3);
  box-shadow: var(--shadow-1);
  overflow: hidden;
  position: sticky;
  top: 70px;
  max-height: calc(100vh - 90px);
  display: flex; flex-direction: column;
}
.tabs {
  display: flex;
  padding: 4px;
  gap: 2px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}
.tabs button {
  flex: 1;
  padding: 7px 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
  background: transparent;
  border: none;
  border-radius: var(--r-1);
  cursor: pointer;
  white-space: nowrap;
  transition: all .12s ease;
}
.tabs button:hover { color: var(--text); }
.tabs button.active {
  background: var(--surface-2);
  color: var(--text);
}
.tab-body {
  flex: 1;
  overflow: auto;
  padding: 14px;
}
.tab-body :deep(.el-card) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}
.tab-body :deep(.el-card__header),
.tab-body :deep(.el-card__body) {
  padding-left: 0 !important;
  padding-right: 0 !important;
}
.stack { display: grid; gap: 14px; }

@media (max-width: 1100px) {
  .task-grid { grid-template-columns: 1fr; }
  .task-right { position: relative; top: 0; max-height: none; }
}
</style>
