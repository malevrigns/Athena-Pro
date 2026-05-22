<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Connection,
  DataAnalysis,
  Document,
  FolderAdd,
  Grid,
  Notebook,
  Refresh,
  Search,
  TrendCharts,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/stores/projects'
import { useEntrance } from '@/composables/useAnime'
import type { ProjectStatus, ResearchProject } from '@/types/research'

const router = useRouter()
const store = useProjectStore()
const search = ref('')
const submitting = ref(false)
const form = reactive({
  title: '',
  research_question: '',
  field: '',
  target_venue: '',
  constraintsText: '',
})

useEntrance('.launch-summary > div, .research-intake, .project-queue, .method-track > div', { delay: (_el, i) => 70 + i * 60 })
useEntrance('.queue-row', { delay: (_el, i) => 260 + i * 35 })

onMounted(() => {
  store.loadProjects()
})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.projects
  return store.projects.filter((project) =>
    [project.title, project.research_question, project.field || '', project.target_venue || '']
      .join('\n')
      .toLowerCase()
      .includes(q),
  )
})

const completedCount = computed(() => store.projects.filter((project) => project.status === 'completed').length)
const waitingCount = computed(() => store.projects.filter((project) => project.status === 'waiting_review').length)

const workflow = [
  { label: 'Literature', icon: Document, text: '检索、筛选、PaperNote' },
  { label: 'Taxonomy', icon: Grid, text: '方法族、演化、问题' },
  { label: 'Baseline', icon: TrendCharts, text: '候选、评分、阻塞选择' },
  { label: 'Idea', icon: Connection, text: '假设、风险、实验计划' },
  { label: 'Experiment', icon: DataAnalysis, text: '复现、配置、框架' },
]

function statusMeta(status: ProjectStatus) {
  const map: Record<ProjectStatus, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
    draft: { label: '草稿', type: 'info' },
    planning: { label: '规划中', type: 'primary' },
    running: { label: '运行中', type: 'primary' },
    waiting_review: { label: '待审批', type: 'warning' },
    completed: { label: '已完成', type: 'success' },
    failed: { label: '失败', type: 'danger' },
    cancelled: { label: '已取消', type: 'info' },
  }
  return map[status]
}

function fmtDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function constraints() {
  return form.constraintsText
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

async function createProject() {
  if (!form.title.trim() || !form.research_question.trim()) {
    ElMessage.warning('请填写标题和研究问题')
    return
  }
  submitting.value = true
  try {
    const project = await store.createProject({
      title: form.title.trim(),
      research_question: form.research_question.trim(),
      field: form.field.trim() || null,
      target_venue: form.target_venue.trim() || null,
      constraints: constraints(),
    })
    ElMessage.success('项目已创建')
    router.push(`/projects/${project.id}`)
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    submitting.value = false
  }
}

function openProject(project: ResearchProject) {
  router.push(`/projects/${project.id}`)
}
</script>

<template>
  <div class="research-launchpad">
    <section class="launch-summary">
      <div>
        <span>Research Projects</span>
        <strong>{{ store.total }}</strong>
      </div>
      <div>
        <span>Active Runs</span>
        <strong>{{ store.activeCount }}</strong>
      </div>
      <div>
        <span>Review Gates</span>
        <strong>{{ waitingCount }}</strong>
      </div>
      <div>
        <span>Completed</span>
        <strong>{{ completedCount }}</strong>
      </div>
    </section>

    <section class="method-track">
      <div v-for="step in workflow" :key="step.label">
        <span><ElIcon><component :is="step.icon" /></ElIcon></span>
        <strong>{{ step.label }}</strong>
        <small>{{ step.text }}</small>
      </div>
    </section>

    <section class="launch-grid">
      <form class="research-intake" @submit.prevent="createProject">
        <header>
          <div class="intake-icon"><ElIcon><FolderAdd /></ElIcon></div>
          <div>
            <div class="head-kicker">Project Intake</div>
            <h2>创建计算机科研项目</h2>
          </div>
        </header>
        <ElInput v-model="form.title" placeholder="项目标题" maxlength="300" show-word-limit />
        <ElInput
          v-model="form.research_question"
          type="textarea"
          :rows="6"
          maxlength="3000"
          show-word-limit
          placeholder="研究问题,例如: 如何复现并改进某类 RAG baseline?"
        />
        <div class="form-row">
          <ElInput v-model="form.field" placeholder="方向,如 LLM evaluation" />
          <ElInput v-model="form.target_venue" placeholder="目标 venue" />
        </div>
        <ElInput
          v-model="form.constraintsText"
          type="textarea"
          :rows="4"
          placeholder="约束条件,每行一条,如 single GPU / public dataset / 2 week deadline"
        />
        <button class="primary-btn lg submit-btn" type="submit" :disabled="submitting">
          <ElIcon><FolderAdd /></ElIcon>
          <span>{{ submitting ? '创建中' : '创建 Research Workspace' }}</span>
        </button>
      </form>

      <section class="project-queue">
        <header class="queue-head">
          <div>
            <div class="head-kicker">Workspace Queue</div>
            <h2>项目队列</h2>
          </div>
          <div class="queue-tools">
            <ElInput v-model="search" :prefix-icon="Search" clearable placeholder="搜索项目、问题、方向" />
            <button class="icon-action" aria-label="刷新" @click="store.loadProjects()">
              <ElIcon><Refresh /></ElIcon>
            </button>
          </div>
        </header>

        <div class="queue-table">
          <button
            v-for="project in filtered"
            :key="project.id"
            class="queue-row"
            @click="openProject(project)"
          >
            <span class="queue-main">
              <strong>{{ project.title }}</strong>
              <small>{{ project.research_question }}</small>
            </span>
            <span class="queue-meta">
              <ElTag :type="statusMeta(project.status).type" effect="light">{{ statusMeta(project.status).label }}</ElTag>
              <small>{{ project.field || '未设置方向' }}</small>
            </span>
            <span class="queue-date mono">{{ fmtDate(project.updated_at) }}</span>
            <span class="row-arrow"><ElIcon><ArrowRight /></ElIcon></span>
          </button>
          <ElEmpty v-if="!filtered.length" description="暂无项目" :image-size="88" />
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.research-launchpad {
  display: grid;
  gap: 16px;
}
.launch-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.launch-summary > div {
  min-height: 82px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 15px 16px;
  display: grid;
  align-content: center;
  gap: 4px;
}
.launch-summary span,
.method-track small,
.queue-main small,
.queue-meta small,
.queue-date {
  color: var(--muted);
  font-size: 12px;
}
.launch-summary strong {
  font-family: var(--t-mono);
  font-size: 28px;
  line-height: 1;
}
.method-track {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.method-track > div {
  min-height: 86px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 12px;
  display: grid;
  align-content: start;
  gap: 6px;
  position: relative;
}
.method-track > div::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 0;
  height: 3px;
  border-radius: 999px 999px 0 0;
  background: var(--primary);
  opacity: .18;
}
.method-track span,
.intake-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: var(--primary-soft);
  color: var(--primary);
}
.method-track strong {
  font-size: 14px;
}
.launch-grid {
  display: grid;
  grid-template-columns: minmax(330px, 430px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.research-intake,
.project-queue {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 20px;
}
.research-intake {
  display: grid;
  gap: 13px;
}
.research-intake header,
.queue-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.research-intake header {
  justify-content: flex-start;
}
.head-kicker {
  color: var(--primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.research-intake h2,
.project-queue h2 {
  margin: 3px 0 0;
  font-size: 17px;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.submit-btn {
  width: 100%;
  justify-content: center;
}
.queue-tools {
  display: grid;
  grid-template-columns: minmax(220px, 320px) 36px;
  gap: 10px;
  align-items: center;
}
.icon-action {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}
.icon-action:hover {
  color: var(--primary);
  border-color: var(--primary-line);
  background: var(--primary-soft);
}
.queue-table {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}
.queue-row {
  width: 100%;
  min-height: 76px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  padding: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px 92px 24px;
  gap: 12px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}
.queue-row:hover {
  border-color: var(--primary-line);
  background: var(--primary-soft);
}
.queue-main,
.queue-meta {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.queue-main strong,
.queue-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-arrow {
  color: var(--muted);
  justify-self: end;
}
@media (max-width: 1180px) {
  .launch-grid,
  .method-track { grid-template-columns: 1fr; }
  .launch-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .launch-summary,
  .form-row,
  .queue-tools,
  .queue-row { grid-template-columns: 1fr; }
  .queue-head { align-items: stretch; flex-direction: column; }
  .row-arrow { justify-self: start; }
}
</style>
