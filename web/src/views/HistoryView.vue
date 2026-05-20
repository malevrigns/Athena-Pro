<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search, View, MoreFilled, Refresh, CaretRight, Filter,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useEntrance, runCountUp } from '@/composables/useAnime'
import { nextTick } from 'vue'

const router = useRouter()
const task = useTaskStore()
const search = ref('')
const status = ref('all')
const dateFrom = ref<Date | null>(null)
const dateTo = ref<Date | null>(null)
const pageSize = ref(10)
const currentPage = ref(1)
const showAdvancedFilters = ref(false)

useEntrance('.hist-stat')
useEntrance('.hist-row', { delay: (_el: HTMLElement, i: number) => 200 + i * 40 })

onMounted(async () => {
  await task.refreshTasks()
  await nextTick()
  runCountUp('.hist-kpi-number')
})

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '进行中', value: 'in-progress' },
  { label: '已完成', value: 'done' },
  { label: '已暂停', value: 'paused' },
  { label: '已终止', value: 'cancelled' },
]

const all = computed(() => [...task.tasks].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')))
const filtered = computed(() => {
  let res = all.value
  const q = search.value.trim().toLowerCase()
  if (q) res = res.filter((t) => t.question.toLowerCase().includes(q) || t.id.includes(q))
  if (status.value !== 'all') {
    res = res.filter((t) => {
      if (status.value === 'done') return t.status === 'done'
      if (status.value === 'cancelled') return t.status === 'cancelled' || t.status === 'failed'
      if (status.value === 'in-progress') return ['planning', 'researching', 'writing', 'quality_gate'].includes(t.status)
      if (status.value === 'paused') return t.status === 'waiting_review'
      return true
    })
  }
  if (dateFrom.value || dateTo.value) {
    res = res.filter((t) => isInDateRange(t.created_at || t.updated_at))
  }
  return res
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)))
const paged = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})
const visiblePages = computed(() => {
  const pages: number[] = []
  const end = Math.min(totalPages.value, 5)
  for (let page = 1; page <= end; page++) pages.push(page)
  return pages
})

function statusTag(s: string) {
  if (s === 'done') return { cls: 'tag-green', label: '已完成' }
  if (s === 'cancelled') return { cls: 'tag', label: '已终止' }
  if (s === 'failed') return { cls: 'tag-red', label: '失败' }
  if (s === 'waiting_review') return { cls: 'tag-purple', label: '已暂停', extra: '可恢复' }
  return { cls: 'tag-blue', label: '进行中' }
}
function statusDot(s: string) {
  const map: Record<string, string> = { done: 'green', cancelled: 'gray', waiting_review: 'purple' }
  return map[s] || 'blue'
}
function fmtDate(iso?: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
function fmtDuration(min: number) {
  if (min < 60) return `${min}分钟`
  return `${Math.floor(min/60)}小时${min%60}分钟`
}
function reset() {
  search.value = ''
  status.value = 'all'
  dateFrom.value = null
  dateTo.value = null
  currentPage.value = 1
}

function isInDateRange(value?: string) {
  if (!value) return false
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return false
  const from = dateFrom.value ? startOfDay(dateFrom.value).getTime() : -Infinity
  const to = dateTo.value ? endOfDay(dateTo.value).getTime() : Infinity
  return time >= from && time <= to
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function endOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 23, 59, 59, 999)
}

function setPage(page: number) {
  currentPage.value = Math.min(Math.max(1, page), totalPages.value)
}

function openTask(id: string) {
  router.push(`/workbench/${id}`)
}

async function resumeTask(id: string) {
  await task.load(id, false)
  if (task.error) {
    ElMessage.error(task.error)
    return
  }
  router.push('/plan-review')
}

function showMoreActions(id: string) {
  ElMessage.info(`更多操作尚未接入后端菜单接口，任务 ID: ${id}`)
}

function toggleAdvancedFilters() {
  showAdvancedFilters.value = !showAdvancedFilters.value
}

watch([search, status, dateFrom, dateTo, pageSize], () => {
  currentPage.value = 1
})

// Right column stats
const totalCount = computed(() => all.value.length)
const doneCount = computed(() => all.value.filter(t => t.status === 'done').length)
const donePct = computed(() => totalCount.value ? Math.round(doneCount.value / totalCount.value * 100) : 0)
const avgCost = computed(() => {
  if (!all.value.length) return 0
  return all.value.reduce((s, t) => s + (t.cost_usd || 0), 0) / all.value.length
})

const pausedTask = computed(() => all.value.find(t => t.status === 'waiting_review'))
const auditRecords = [
  { type: 'plan', title: '研究计划 - AI Agent 商业化路径分析', status: 'pass',  name: 'Plan Review',       date: '05-07 11:23' },
  { type: 'cite', title: '引用验证 - 关键引用集 (48条)',       status: 'pass',  name: 'Citation Validator', date: '05-06 18:42' },
  { type: 'plan', title: '研究计划 - 医疗影像多模态研究',       status: 'wait',  name: 'Plan Review',       date: '05-05 14:11' },
  { type: 'cite', title: '引用验证 - RAG 技术演进 (35条)',     status: 'pass',  name: 'Citation Validator', date: '05-04 16:32' },
  { type: 'plan', title: '研究计划 - 金融行业合规研究',         status: 'pass',  name: 'Plan Review',       date: '05-03 09:01' },
]
</script>

<template>
  <div class="hist">
    <div class="hist-grid">
      <!-- Left: table -->
      <div class="hist-main">
        <!-- Filter bar -->
        <section class="card filter-bar">
          <ElInput v-model="search" placeholder="搜索任务名称、ID 或关键词" :prefix-icon="Search" clearable class="filter-search" />
          <div class="filter-field">
            <span class="filter-label">状态</span>
            <ElSelect v-model="status" size="default" style="width: 140px;">
              <ElOption v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
            </ElSelect>
          </div>
          <div v-show="showAdvancedFilters" class="filter-field">
            <span class="filter-label">创建时间</span>
            <ElDatePicker
              v-model="dateFrom" type="date" placeholder="开始日期" size="default"
              style="width: 140px;" :clearable="true"
            />
            <span class="date-arrow">→</span>
            <ElDatePicker
              v-model="dateTo" type="date" placeholder="结束日期" size="default"
              style="width: 140px;" :clearable="true"
            />
          </div>
          <button class="btn-secondary" @click="reset"><ElIcon><Refresh /></ElIcon><span>重置</span></button>
          <button class="btn-secondary" @click="toggleAdvancedFilters"><ElIcon><Filter /></ElIcon><span>更多筛选</span></button>
        </section>

        <!-- Table -->
        <section class="card hist-table">
          <div class="th-row">
            <div>任务名称</div>
            <div>创建时间 <span class="th-sort">⇅</span></div>
            <div>状态</div>
            <div>成本 (USD)</div>
            <div>耗时</div>
            <div>操作</div>
          </div>
          <div v-for="t in paged" :key="t.id" class="td-row hist-row" @click="openTask(t.id)">
            <div class="td-task">
              <div class="td-icon" :data-color="statusDot(t.status)"><span /></div>
              <div>
                <div class="td-task-name">{{ t.question }}</div>
                <div class="td-task-id">ID: {{ t.id }}</div>
              </div>
            </div>
            <div class="td-time">{{ fmtDate(t.updated_at) }}</div>
            <div>
              <span class="tag" :class="statusTag(t.status).cls">
                <i v-if="statusTag(t.status).cls !== 'tag'" />
                {{ statusTag(t.status).label }}
              </span>
              <span v-if="statusTag(t.status).extra" class="tag tag-purple ml4">{{ statusTag(t.status).extra }}</span>
            </div>
            <div class="td-cost">${{ (t.cost_usd || 0).toFixed(2) }}</div>
            <div class="td-duration">{{ fmtDuration(Math.max(10, Math.floor((t.cost_usd || 0) * 6))) }}</div>
            <div class="td-actions">
              <button v-if="t.status === 'waiting_review'" class="resume-btn" @click.stop="resumeTask(t.id)">恢复</button>
              <button class="td-ico-btn" v-else @click.stop="openTask(t.id)"><ElIcon><View /></ElIcon></button>
              <button class="td-ico-btn" @click.stop="showMoreActions(t.id)"><ElIcon><MoreFilled /></ElIcon></button>
            </div>
          </div>
          <ElEmpty v-if="!filtered.length" description="没有匹配的任务" :image-size="80" />

          <div class="hist-pager">
            <span class="pager-count">共 {{ filtered.length }} 条</span>
            <div class="pager-mid">
              <button :disabled="currentPage <= 1" @click="setPage(currentPage - 1)"><ElIcon><CaretRight style="transform: rotate(180deg);" /></ElIcon></button>
              <button
                v-for="page in visiblePages"
                :key="page"
                :class="{ active: currentPage === page }"
                @click="setPage(page)"
              >{{ page }}</button>
              <span v-if="totalPages > 6">…</span>
              <button v-if="totalPages > 5" :class="{ active: currentPage === totalPages }" @click="setPage(totalPages)">{{ totalPages }}</button>
              <button :disabled="currentPage >= totalPages" @click="setPage(currentPage + 1)"><ElIcon><CaretRight /></ElIcon></button>
            </div>
            <ElSelect v-model="pageSize" size="default" style="width: 90px;">
              <ElOption label="10 条/页" :value="10" />
              <ElOption label="20 条/页" :value="20" />
              <ElOption label="50 条/页" :value="50" />
            </ElSelect>
          </div>
        </section>
      </div>

      <!-- Right: stats + paused + audit -->
      <div class="hist-side">
        <div class="kpi-grid">
          <article class="kpi-card hist-stat">
            <div class="kpi-ico" data-color="blue"><span class="material-ico">📄</span></div>
            <div class="kpi-label">历史任务总数</div>
            <div class="kpi-value hist-kpi-number" :data-value="totalCount || 0">0</div>
            <div class="kpi-sub">所有时间</div>
          </article>
          <article class="kpi-card hist-stat">
            <div class="kpi-ico" data-color="green"><span class="material-ico">✓</span></div>
            <div class="kpi-label">已完成任务</div>
            <div class="kpi-value hist-kpi-number" :data-value="doneCount || 0">0</div>
            <div class="kpi-sub">占比 {{ donePct || '0' }}%</div>
          </article>
          <article class="kpi-card hist-stat">
            <div class="kpi-ico" data-color="orange"><span class="material-ico">$</span></div>
            <div class="kpi-label">平均成本</div>
            <div class="kpi-value hist-kpi-number" :data-value="avgCost || 0" data-precision="2" data-prefix="$ ">0</div>
            <div class="kpi-sub">USD</div>
          </article>
          <article class="kpi-card hist-stat">
            <div class="kpi-ico" data-color="purple"><span class="material-ico">⏱</span></div>
            <div class="kpi-label">任务总数</div>
            <div class="kpi-value hist-kpi-number" :data-value="totalCount || 0">0</div>
            <div class="kpi-sub">含未完成</div>
          </article>
        </div>

        <article v-if="pausedTask" class="card paused-card">
          <header class="section-head">
            <h3 class="card-title">继续上次任务</h3>
            <span class="tag tag-purple">已暂停</span>
          </header>
          <div class="paused-body">
            <div class="paused-icon">📄</div>
            <div>
              <div class="paused-title">{{ pausedTask.question }}</div>
              <div class="paused-id">ID: {{ pausedTask.id }}</div>
            </div>
          </div>
          <div class="paused-progress">
            <div class="kv-line"><span>进度 42%</span></div>
            <div class="rp-bar"><i style="width: 42%; background: var(--purple);" /></div>
            <div class="paused-meta">暂停时间:2025-05-02 16:48</div>
          </div>
          <button class="primary-btn block-btn" @click="resumeTask(pausedTask.id)">恢复任务</button>
        </article>

        <article class="card audit-card">
          <header class="section-head">
            <h3 class="card-title">最近审批记录</h3>
            <a class="link-mini">查看全部</a>
          </header>
          <ul class="audit-list">
            <li v-for="(a, i) in auditRecords" :key="i">
              <span class="audit-dot" :data-status="a.status">
                <span v-if="a.status === 'pass'">✓</span>
                <span v-else>!</span>
              </span>
              <div class="audit-body">
                <div class="audit-title">{{ a.title }}</div>
                <div class="audit-foot">
                  <span class="audit-status" :data-status="a.status">{{ a.status === 'pass' ? '已通过' : '待修改' }}</span>
                  <span class="audit-sep">·</span>
                  <span class="audit-name">{{ a.name }}</span>
                </div>
              </div>
              <div class="audit-time">{{ a.date }}</div>
            </li>
          </ul>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hist-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}
.hist-main, .hist-side { display: grid; gap: 16px; min-width: 0; }

/* Filter bar */
.filter-bar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 14px 18px;
}
.filter-search { flex: 1; min-width: 260px; max-width: 320px; }
.filter-field { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 12.5px; color: var(--muted); font-weight: 500; }
.date-arrow { color: var(--muted-soft); }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .12s ease;
}
.btn-secondary:hover { border-color: var(--primary-line); color: var(--primary); }

/* Table */
.hist-table { padding: 0; overflow: hidden; }
.th-row, .td-row {
  display: grid;
  grid-template-columns: 2.4fr 1.1fr 1fr .7fr .7fr 90px;
  align-items: center;
  gap: 12px;
  padding: 14px 22px;
  font-size: 13px;
}
.th-row {
  background: var(--surface-3);
  color: var(--text-soft);
  font-size: 12.5px;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}
.th-sort { color: var(--muted-soft); margin-left: 2px; font-size: 11px; }
.td-row {
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background .1s ease;
}
.td-row:hover { background: var(--surface-2); }
.td-row:last-of-type { border-bottom: none; }

.td-task { display: flex; align-items: center; gap: 10px; min-width: 0; }
.td-icon { width: 28px; height: 28px; border-radius: 6px; display: grid; place-items: center; flex-shrink: 0; }
.td-icon[data-color='blue']   { background: #dbeafe; }
.td-icon[data-color='green']  { background: #dcfce7; }
.td-icon[data-color='purple'] { background: #ede9fe; }
.td-icon[data-color='gray']   { background: #f3f4f6; }
.td-icon span {
  display: block;
  width: 12px; height: 14px;
  background:
    linear-gradient(var(--surface) 0%, var(--surface) 14%, transparent 14%) 0 0 / 100% 100%,
    var(--primary);
  -webkit-mask: linear-gradient(135deg, transparent 33%, #000 33%);
          mask: linear-gradient(135deg, transparent 33%, #000 33%);
}
.td-task-name {
  font-size: 13.5px; font-weight: 500; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 360px;
}
.td-task-id { font-size: 11.5px; color: var(--muted); font-family: var(--t-mono); margin-top: 2px; }
.td-time { color: var(--muted); font-size: 12.5px; }
.td-cost { color: var(--text); font-weight: 600; font-size: 13px; font-family: var(--t-mono); }
.td-duration { color: var(--muted); font-size: 12.5px; }
.td-actions { display: flex; gap: 4px; align-items: center; }
.td-ico-btn {
  width: 28px; height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  display: grid; place-items: center;
}
.td-ico-btn:hover { background: var(--surface-3); color: var(--primary); }
.resume-btn {
  height: 28px; padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--primary-line);
  background: var(--primary-soft);
  color: var(--primary);
  font: inherit; font-weight: 500; font-size: 12.5px;
  cursor: pointer;
}
.resume-btn:hover { background: var(--primary); color: white; }

.ml4 { margin-left: 4px; }
.tag i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; margin-right: 2px; }

/* Pager */
.hist-pager {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 22px;
  border-top: 1px solid var(--border);
}
.pager-count { color: var(--muted); font-size: 12.5px; }
.pager-mid { display: flex; align-items: center; gap: 4px; }
.pager-mid button {
  min-width: 28px; height: 28px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 12.5px;
  border-radius: 6px;
  cursor: pointer;
  padding: 0 8px;
}
.pager-mid button:hover { border-color: var(--primary-line); color: var(--primary); }
.pager-mid button.active { background: var(--primary); border-color: var(--primary); color: white; }
.pager-mid span { color: var(--muted-soft); padding: 0 4px; }

/* KPI grid */
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.kpi-card {
  position: relative;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-1);
}
.kpi-ico {
  position: absolute; top: 14px; right: 14px;
  width: 28px; height: 28px;
  border-radius: 7px;
  display: grid; place-items: center;
  font-size: 14px;
  font-weight: 700;
}
.kpi-ico[data-color='blue']   { background: #dbeafe; color: #2563eb; }
.kpi-ico[data-color='green']  { background: #dcfce7; color: #16a34a; }
.kpi-ico[data-color='orange'] { background: #ffedd5; color: #f97316; }
.kpi-ico[data-color='purple'] { background: #ede9fe; color: #7c3aed; }
.kpi-label { font-size: 12.5px; color: var(--muted); margin-bottom: 6px; }
.kpi-value { font-size: 24px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; }
.kpi-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* Paused card */
.paused-card { padding: 16px 18px; }
.section-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.paused-body { display: flex; gap: 10px; align-items: flex-start; padding: 4px 0 10px; }
.paused-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: #ede9fe; display: grid; place-items: center;
  font-size: 16px;
}
.paused-title { font-size: 13.5px; font-weight: 600; color: var(--text); line-height: 1.3; }
.paused-id { font-size: 11.5px; color: var(--muted); font-family: var(--t-mono); margin-top: 2px; }
.paused-progress { margin-top: 4px; }
.kv-line { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-soft); margin-bottom: 4px; }
.rp-bar { height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.rp-bar i { display: block; height: 100%; border-radius: inherit; }
.paused-meta { font-size: 11.5px; color: var(--muted); margin-top: 6px; }
.block-btn { width: 100%; margin-top: 12px; }

/* Audit */
.audit-card { padding: 16px 18px; }
.link-mini { font-size: 12px; color: var(--primary); cursor: pointer; }
.audit-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 14px; }
.audit-list li { display: flex; align-items: flex-start; gap: 10px; }
.audit-dot {
  width: 18px; height: 18px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 11px; font-weight: 700;
  flex-shrink: 0;
}
.audit-dot[data-status='pass'] { background: var(--green-soft); color: var(--green); }
.audit-dot[data-status='wait'] { background: var(--orange-soft); color: var(--orange); }
.audit-body { flex: 1; min-width: 0; }
.audit-title {
  font-size: 12.5px; font-weight: 500; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.audit-foot { display: flex; align-items: center; gap: 4px; margin-top: 2px; font-size: 11px; color: var(--muted); }
.audit-status[data-status='pass'] { color: var(--green); font-weight: 600; }
.audit-status[data-status='wait'] { color: var(--orange); font-weight: 600; }
.audit-sep { color: var(--muted-soft); }
.audit-time { font-size: 11px; color: var(--muted-soft); font-family: var(--t-mono); flex-shrink: 0; }

@media (max-width: 1200px) {
  .hist-grid { grid-template-columns: 1fr; }
}
</style>
