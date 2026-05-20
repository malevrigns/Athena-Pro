<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Download, Document, Share, MoreFilled, Star, FullScreen, Filter,
  ArrowRight, Right, Promotion,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { useEntrance } from '@/composables/useAnime'
import type { Citation, FinalReport } from '@/types/api'

useEntrance('.rep-kpi .kpi-cell')
useEntrance('.src-card', { delay: (_el, i) => 150 + i * 50, translateX: [12, 0] as any, translateY: undefined as any })
useEntrance('.rep-body, .rep-toc, .rep-sources', { delay: (_el, i) => 100 + i * 80 })

const task = useTaskStore()
const session = useSessionStore()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const selectedTaskId = ref<string>('')
const sourceFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const focusMode = ref(false)
const moreDialog = ref(false)
const FAVORITES_KEY = 'athena.reportFavorites'
const favoriteIds = ref<Set<string>>(new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')))

onMounted(async () => {
  if (!task.tasks.length) await task.refreshTasks()
  // Prefer task currently in store, then most recent done task with a report
  if (task.current?.final_report) {
    selectedTaskId.value = task.current.id
  } else {
    const candidate = [...task.tasks]
      .filter((t) => t.final_report)
      .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))[0]
    if (candidate) {
      selectedTaskId.value = candidate.id
      await task.load(candidate.id, false)
    }
  }
})

const allReports = computed(() =>
  [...task.tasks]
    .filter((t) => t.final_report)
    .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')),
)

const currentReport = computed<FinalReport | null>(() => task.finalReport)
const reportTitle = computed(() => currentReport.value?.title || task.current?.question || '尚未选择报告')
const finishTime = computed(() => task.current?.updated_at || '')
const reportMarkdown = computed(() => currentReport.value?.markdown || '')

// KPI computed from real quality
const overall = computed(() => task.quality?.overall ?? currentReport.value?.quality?.overall ?? 0)
const factuality = computed(() => task.quality?.factuality ?? currentReport.value?.quality?.factuality ?? 0)
const citationIntegrity = computed(() => task.quality?.citation_integrity ?? currentReport.value?.quality?.citation_integrity ?? 0)
const finalCost = computed(() => task.current?.cost_usd ?? 0)

function rating(score: number): { label: string; cls: string } {
  if (score >= 0.85) return { label: '优秀', cls: 'tag-green' }
  if (score >= 0.6)  return { label: '良好', cls: 'tag-blue' }
  if (score >= 0.4)  return { label: '一般', cls: 'tag-orange' }
  return { label: '欠佳', cls: 'tag-red' }
}

// TOC derived from the markdown headings
interface TocItem { id: string; level: number; text: string; pos: number }
const toc = computed<TocItem[]>(() => {
  const out: TocItem[] = []
  const lines = reportMarkdown.value.split('\n')
  let pos = 0
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,3})\s+(.+)$/)
    if (m) {
      const level = m[1].length
      out.push({ id: `h-${i}`, level, text: m[2].trim(), pos: pos })
      pos++
    }
  }
  return out
})

const activeTocId = ref<string>('')
watch(toc, (val) => {
  if (val.length && !activeTocId.value) activeTocId.value = val[0].id
})

// Real markdown render — inject anchors on headings and replace [n] with hover triggers
const renderedHtml = computed(() => {
  const raw = reportMarkdown.value
  if (!raw) return ''
  let html = md.render(raw)
  // Add id to headings to match TOC entries
  let idx = 0
  html = html.replace(/<h([1-3])>/g, (_, lv) => `<h${lv} id="h-anchor-${idx++}" class="rep-heading">`)
  // Replace [n] citation markers with hoverable spans
  html = html.replace(/\[(\d+)\]/g, (_, num) => `<span class="cite" data-cite="${num}">[${num}]</span>`)
  return DOMPurify.sanitize(html, { ADD_ATTR: ['data-cite'] })
})

// Citation sources from the real report
function sourceMeta(c: Citation) {
  let host = ''
  try { host = new URL(c.url).hostname } catch {}
  let logo = (host.split('.')[1] || host || c.title).slice(0, 3).toUpperCase()
  if (!logo) logo = 'SRC'
  // Confidence heuristic: known sources high; mock URLs low; rest medium
  let confidence: 'high' | 'medium' | 'low' = 'medium'
  if (/idc|gartner|mckinsey|forrester|bcg/i.test(c.url + c.title)) confidence = 'high'
  else if (c.url.startsWith('https://example.com')) confidence = 'low'
  const match = confidence === 'high' ? 92 : confidence === 'medium' ? 72 : 42
  return { host, logo, confidence, match }
}

const citationsWithMeta = computed(() => {
  const list = currentReport.value?.citations ?? []
  return list.map((c) => ({ ...c, ...sourceMeta(c) }))
})

const filteredCitations = computed(() => {
  if (sourceFilter.value === 'all') return citationsWithMeta.value
  return citationsWithMeta.value.filter((c) => c.confidence === sourceFilter.value)
})

function confidenceMeta(c: string) {
  if (c === 'high')   return { color: 'green',  label: '高置信度' }
  if (c === 'medium') return { color: 'orange', label: '中等置信度' }
  return { color: 'red', label: '低置信度' }
}

// Hover popover state
const hoverCite = ref<{ n: number; x: number; y: number } | null>(null)
function handleReportHover(ev: MouseEvent) {
  const t = ev.target as HTMLElement
  if (t?.dataset?.cite) {
    const n = Number(t.dataset.cite)
    const rect = t.getBoundingClientRect()
    const reportRect = (ev.currentTarget as HTMLElement).getBoundingClientRect()
    hoverCite.value = { n, x: rect.left - reportRect.left + rect.width / 2, y: rect.bottom - reportRect.top + 6 }
  }
}
function handleReportLeave(ev: MouseEvent) {
  const t = ev.target as HTMLElement
  if (t?.dataset?.cite) hoverCite.value = null
}
const hoveredCitation = computed(() => {
  if (!hoverCite.value) return null
  return citationsWithMeta.value.find((c) => c.number === hoverCite.value!.n) || null
})

function scrollToHeading(item: TocItem) {
  activeTocId.value = item.id
  const target = document.querySelector(`#h-anchor-${item.pos}`)
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  ElMessage.info(`已定位章节:${item.text}`)
}

async function loadReport(id: string) {
  selectedTaskId.value = id
  await task.load(id, false)
}

async function exportFmt(fmt: 'md' | 'html' | 'pdf' | 'docx') {
  if (!task.current?.id) {
    ElMessage.warning('未选中任务')
    return
  }
  try {
    await task.downloadReport(fmt)
    ElMessage.success(`已下载 ${fmt.toUpperCase()}`)
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
async function copyMarkdown() {
  if (!reportMarkdown.value) return
  await navigator.clipboard.writeText(reportMarkdown.value)
  ElMessage.success('已复制 Markdown')
}

function showMissingReportAction(action: string) {
  if (action === '更多报告操作') {
    moreDialog.value = true
    return
  }
  ElMessage.info(action)
}

function toggleFocusMode() {
  focusMode.value = !focusMode.value
}

const isFavorite = computed(() => Boolean(task.current?.id && favoriteIds.value.has(task.current.id)))

function toggleFavorite() {
  if (!task.current?.id) {
    ElMessage.warning('未选中任务')
    return
  }
  const next = new Set(favoriteIds.value)
  if (next.has(task.current.id)) next.delete(task.current.id)
  else next.add(task.current.id)
  favoriteIds.value = next
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...next]))
  ElMessage.success(next.has(task.current.id) ? '已收藏报告' : '已取消收藏')
}

function openSource(url: string, number: number) {
  window.open(url, '_blank', 'noopener,noreferrer')
  ElMessage.info(`已打开来源 [${number}]`)
}
</script>

<template>
  <div class="rep">
    <!-- Task picker when there are multiple reports -->
    <section v-if="allReports.length > 1" class="rep-picker reports-list">
      <span class="picker-label">选择报告</span>
      <ElSelect :model-value="selectedTaskId" @update:model-value="loadReport" size="default" style="width: 360px;">
        <ElOption v-for="t in allReports" :key="t.id" :label="t.question" :value="t.id" />
      </ElSelect>
    </section>

    <ElEmpty v-if="!currentReport" description="尚未生成任何研究报告。前往「研究台」开启第一次研究。">
      <ElButton type="primary" :icon="Promotion" @click="$router.push('/')">开始研究</ElButton>
    </ElEmpty>

    <template v-else>
      <!-- KPI bar (real data) -->
      <section class="rep-kpi card">
        <div class="kpi-cell">
          <div class="kpi-label">整体质量评分</div>
          <div class="kpi-line">
            <span class="kpi-big primary">{{ (overall * 100).toFixed(0) }}</span><span class="kpi-unit">/100</span>
            <span class="tag" :class="rating(overall).cls">{{ rating(overall).label }}</span>
          </div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">引用覆盖率</div>
          <div class="kpi-line">
            <span class="kpi-big primary">{{ (citationIntegrity * 100).toFixed(0) }}%</span>
            <span class="tag" :class="rating(citationIntegrity).cls">{{ rating(citationIntegrity).label }}</span>
          </div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">事实一致性</div>
          <div class="kpi-line">
            <span class="kpi-big primary">{{ (factuality * 100).toFixed(0) }}%</span>
            <span class="tag" :class="rating(factuality).cls">{{ rating(factuality).label }}</span>
          </div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">实际成本</div>
          <div class="kpi-line">
            <span class="kpi-big">$ {{ finalCost.toFixed(2) }}</span><span class="kpi-unit">USD</span>
          </div>
        </div>
        <div class="kpi-actions">
          <div class="action-row">
            <button class="btn-secondary" :disabled="!session.config?.export_formats?.pdf" @click="exportFmt('pdf')">
              <ElIcon><Document /></ElIcon><span>导出 PDF</span>
            </button>
            <button class="btn-secondary" @click="exportFmt('md')">
              <ElIcon><Download /></ElIcon><span>导出 Markdown</span>
            </button>
          </div>
          <div class="action-row">
            <button class="btn-secondary" @click="copyMarkdown"><ElIcon><Share /></ElIcon><span>复制全文</span></button>
            <button class="btn-secondary square" @click="showMissingReportAction('更多报告操作')"><ElIcon><MoreFilled /></ElIcon></button>
          </div>
        </div>
      </section>

      <!-- 3-col layout -->
      <section class="rep-grid" :class="{ focus: focusMode }">
        <!-- TOC derived from real report -->
        <aside class="card rep-toc">
          <header class="rep-toc-head"><h3>目录</h3></header>
          <ElEmpty v-if="!toc.length" :image-size="48" description="未识别到章节" />
          <ul v-else>
            <li v-for="t in toc" :key="t.id">
              <div
                class="toc-item"
                :class="{ active: activeTocId === t.id, 'l-1': t.level === 1, 'l-2': t.level === 2, 'l-3': t.level === 3 }"
                @click="scrollToHeading(t)"
              >
                <span>{{ t.text }}</span>
              </div>
            </li>
          </ul>
        </aside>

        <!-- Report body -->
        <article class="card rep-body">
          <header class="rep-body-head">
            <div>
              <h2>{{ reportTitle }}</h2>
              <div class="rep-meta">
                <span class="tag tag-green"><i />已完成</span>
                <span class="rep-time" v-if="finishTime">完成时间:{{ new Date(finishTime).toLocaleString('zh-CN') }}</span>
                <span class="rep-time">任务 ID:<code>{{ task.current?.id }}</code></span>
              </div>
            </div>
            <div class="rep-body-actions">
              <button class="ico-btn-sm" :class="{ active: isFavorite }" @click="toggleFavorite"><ElIcon><Star /></ElIcon></button>
              <button class="ico-btn-sm" @click="toggleFocusMode"><ElIcon><FullScreen /></ElIcon></button>
            </div>
          </header>

          <div
            class="rep-content"
            @mouseover="handleReportHover"
            @mouseout="handleReportLeave"
            v-html="renderedHtml"
          />

          <!-- hover popover with real citation data -->
          <div
            v-if="hoverCite && hoveredCitation"
            class="cite-pop"
            :style="{ left: `${hoverCite.x}px`, top: `${hoverCite.y}px` }"
          >
            <div class="cp-head">
              <span class="cp-cite">引用 [{{ hoveredCitation.number }}]</span>
              <span class="tag" :class="`tag-${confidenceMeta(hoveredCitation.confidence).color}`">{{ confidenceMeta(hoveredCitation.confidence).label }}</span>
            </div>
            <div class="cp-body">
              <div class="cp-logo">{{ hoveredCitation.logo }}</div>
              <div style="min-width: 0;">
                <div class="cp-name">{{ hoveredCitation.title }}</div>
                <div class="cp-time" v-if="hoveredCitation.host">{{ hoveredCitation.host }}</div>
                <p v-if="hoveredCitation.quote">{{ hoveredCitation.quote }}</p>
                <a class="cp-link" :href="hoveredCitation.url" target="_blank" rel="noopener noreferrer">在右侧查看来源 <ElIcon><ArrowRight /></ElIcon></a>
              </div>
            </div>
          </div>
        </article>

        <!-- Sources sidebar (real) -->
        <aside class="card rep-sources">
          <header class="rep-sources-head">
            <div>
              <h3>引用溯源</h3>
              <small>{{ citationsWithMeta.length }}</small>
            </div>
          </header>
          <div class="src-filter">
            <ElSelect v-model="sourceFilter" size="default" style="flex:1;">
              <ElOption label="全部来源" value="all" />
              <ElOption label="高置信度" value="high" />
              <ElOption label="中等置信度" value="medium" />
              <ElOption label="低置信度" value="low" />
            </ElSelect>
            <button class="btn-secondary square" @click="sourceFilter = 'all'"><ElIcon><Filter /></ElIcon></button>
          </div>
          <ElEmpty v-if="!filteredCitations.length" :image-size="48" description="没有匹配的来源" />
          <div class="src-list">
            <article v-for="s in filteredCitations" :key="s.number" class="src-card" @click="openSource(s.url, s.number)">
              <div class="src-head">
                <div class="src-logo">{{ s.logo }}</div>
                <div class="src-name">
                  <div class="src-n">{{ s.number }}</div>
                  <strong>{{ s.host || s.title.slice(0, 14) }}</strong>
                </div>
                <span class="tag" :class="`tag-${confidenceMeta(s.confidence).color}`">{{ confidenceMeta(s.confidence).label }}</span>
              </div>
              <div class="src-title" :title="s.title">{{ s.title }}</div>
              <p v-if="s.quote">{{ s.quote }}</p>
              <div class="src-foot">
                <span>匹配度 {{ s.match }}%</span>
                <div class="src-bar"><i :style="{ width: s.match + '%', background: confidenceMeta(s.confidence).color === 'green' ? 'var(--green)' : confidenceMeta(s.confidence).color === 'orange' ? 'var(--orange)' : 'var(--red)' }" /></div>
              </div>
              <a class="src-link" :href="s.url" target="_blank" rel="noopener noreferrer" @click.stop>{{ s.url }}</a>
            </article>
          </div>
        </aside>
      </section>
    </template>

    <ElDialog v-model="moreDialog" title="报告操作" width="420px">
      <div class="more-actions">
        <ElButton @click="copyMarkdown">复制 Markdown</ElButton>
        <ElButton @click="exportFmt('md')">导出 Markdown</ElButton>
        <ElButton :disabled="!session.config?.export_formats?.html" @click="exportFmt('html')">导出 HTML</ElButton>
        <ElButton @click="toggleFavorite">{{ isFavorite ? '取消收藏' : '收藏报告' }}</ElButton>
      </div>
    </ElDialog>
  </div>
</template>

<style scoped>
.rep { display: grid; gap: 16px; }

.rep-picker { display: flex; align-items: center; gap: 10px; padding: 0 4px; }
.picker-label { font-size: 12.5px; color: var(--muted); }

/* KPI */
.rep-kpi {
  display: grid;
  grid-template-columns: repeat(4, 1fr) 320px;
  gap: 24px;
  padding: 18px 22px;
  align-items: center;
}
.kpi-cell { display: grid; gap: 4px; }
.kpi-label { font-size: 12.5px; color: var(--muted); }
.kpi-line { display: flex; align-items: baseline; gap: 8px; }
.kpi-big { font-size: 30px; font-weight: 800; color: var(--text); letter-spacing: -.02em; line-height: 1.1; font-family: var(--t-mono); }
.kpi-big.primary { color: var(--primary); }
.kpi-unit { font-size: 12px; color: var(--muted); }
.kpi-actions { display: grid; gap: 8px; }
.action-row { display: flex; gap: 8px; }
.action-row .btn-secondary { flex: 1; justify-content: center; }
.action-row .btn-secondary.square { flex: 0 0 38px; padding: 0; justify-content: center; }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 38px; padding: 0 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer;
}
.btn-secondary:hover:not(:disabled) { border-color: var(--primary-line); color: var(--primary); }
.btn-secondary:disabled { opacity: .5; cursor: not-allowed; }

/* Grid */
.rep-grid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}
.rep-grid.focus {
  grid-template-columns: minmax(0, 1fr);
}
.rep-grid.focus .rep-toc,
.rep-grid.focus .rep-sources {
  display: none;
}

/* TOC */
.rep-toc { padding: 16px 14px; }
.rep-toc-head h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text); padding: 0 6px; }
.rep-toc ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 2px; }
.toc-item {
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-soft);
  cursor: pointer;
  transition: background .12s ease;
}
.toc-item:hover { background: var(--surface-2); }
.toc-item.active {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}
.toc-item.l-1 { font-weight: 600; }
.toc-item.l-2 { padding-left: 18px; }
.toc-item.l-3 { padding-left: 26px; color: var(--muted); }
.toc-item.l-3.active { color: var(--primary); }

/* Body */
.rep-body { padding: 22px 28px; position: relative; }
.rep-body-head { display: flex; justify-content: space-between; align-items: flex-start; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
.rep-body-head h2 { margin: 0; font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -.015em; max-width: 640px; }
.rep-meta { display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.rep-time { font-size: 12px; color: var(--muted); font-family: var(--t-mono); }
.rep-time code { font-family: var(--t-mono); color: var(--text-soft); }
.rep-body-actions { display: flex; gap: 4px; flex-shrink: 0; }
.rep-body-actions .active { color: var(--orange); background: var(--orange-soft); }
.ico-btn-sm {
  width: 30px; height: 30px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--surface);
  color: var(--muted); cursor: pointer;
  display: grid; place-items: center;
}
.ico-btn-sm:hover { color: var(--primary); border-color: var(--primary-line); }

.rep-content {
  padding: 18px 0 8px;
  font-size: 13.5px; line-height: 1.85; color: var(--text-soft);
  position: relative;
}
.rep-content :deep(h1) { font-size: 20px; font-weight: 700; color: var(--text); margin: 18px 0 12px; }
.rep-content :deep(h2) { font-size: 17px; font-weight: 700; color: var(--text); margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.rep-content :deep(h3) { font-size: 15px; font-weight: 600; color: var(--text); margin: 16px 0 8px; }
.rep-content :deep(p) { margin: 0 0 14px; }
.rep-content :deep(ul), .rep-content :deep(ol) { padding-left: 20px; margin: 0 0 14px; }
.rep-content :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.rep-content :deep(th), .rep-content :deep(td) { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
.rep-content :deep(th) { background: var(--surface-3); font-weight: 600; color: var(--text-soft); }
.rep-content :deep(a) { color: var(--primary); }
.rep-content :deep(code) { font-family: var(--t-mono); background: var(--primary-soft); color: var(--primary); padding: 2px 6px; border-radius: 4px; font-size: 92%; }
.rep-content :deep(blockquote) { border-left: 3px solid var(--primary); padding: 4px 12px; color: var(--muted); margin: 8px 0; }
.rep-content :deep(.cite) {
  display: inline-block;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--t-mono);
  margin: 0 1px;
  cursor: pointer;
  vertical-align: super;
  transition: background .12s ease;
}
.rep-content :deep(.cite:hover) {
  background: var(--primary);
  color: white;
}

/* Hover popover */
.cite-pop {
  position: absolute;
  transform: translateX(-50%);
  width: 320px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15,23,42,.16);
  padding: 14px;
  z-index: 50;
  pointer-events: none;
}
.cp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.cp-cite { font-size: 13px; font-weight: 600; color: var(--text); font-family: var(--t-mono); }
.cp-body { display: flex; gap: 12px; align-items: flex-start; }
.cp-logo {
  width: 36px; height: 36px; border-radius: 8px;
  background: var(--primary); color: white;
  display: grid; place-items: center;
  font-weight: 700; font-size: 11px; font-family: var(--t-mono);
  flex-shrink: 0;
}
.cp-body strong { font-size: 13px; color: var(--text); }
.cp-name { font-size: 12.5px; color: var(--text); font-weight: 600; line-height: 1.4; }
.cp-time { font-size: 11.5px; color: var(--muted); margin-top: 2px; font-family: var(--t-mono); }
.cp-body p { margin: 8px 0 6px; font-size: 12px; color: var(--muted); line-height: 1.5; }
.cp-link { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--primary); pointer-events: auto; }

/* Sources */
.rep-sources { padding: 16px 14px; }
.rep-sources-head { display: flex; justify-content: space-between; align-items: center; padding: 0 6px; margin-bottom: 12px; }
.rep-sources-head h3 { margin: 0; font-size: 14px; font-weight: 600; display: inline-block; }
.rep-sources-head small { color: var(--muted); margin-left: 6px; }
.src-filter { display: flex; gap: 6px; margin-bottom: 12px; padding: 0 6px; }
.src-filter .btn-secondary.square { width: 38px; padding: 0; justify-content: center; }
.src-list { display: grid; gap: 10px; max-height: 700px; overflow: auto; padding-right: 4px; }
.src-card { padding: 12px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); cursor: pointer; }
.src-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.src-logo {
  width: 26px; height: 26px; border-radius: 6px;
  background: var(--primary-soft); color: var(--primary);
  display: grid; place-items: center;
  font-weight: 700; font-size: 10px; font-family: var(--t-mono);
}
.src-name { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; }
.src-n {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--surface-3); color: var(--muted);
  display: grid; place-items: center;
  font-size: 10px; font-family: var(--t-mono); font-weight: 700;
  flex-shrink: 0;
}
.src-name strong {
  font-size: 13px; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-title {
  font-size: 12.5px; font-weight: 500; color: var(--text-soft);
  margin: 6px 0 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.src-card p {
  margin: 6px 0; font-size: 11.5px; color: var(--muted); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.src-foot { display: grid; grid-template-columns: 100px 1fr; gap: 8px; align-items: center; font-size: 11px; color: var(--muted); }
.src-bar { height: 3px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.src-bar i { display: block; height: 100%; }
.src-link {
  display: block; margin-top: 8px;
  font-size: 10.5px; color: var(--muted-soft);
  font-family: var(--t-mono);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-link:hover { color: var(--primary); }

.more-actions { display: grid; gap: 10px; }
.more-actions .el-button { justify-content: flex-start; margin-left: 0; }

@media (max-width: 1500px) {
  .rep-kpi { grid-template-columns: repeat(4, 1fr); }
  .kpi-actions { display: none; }
}
@media (max-width: 1300px) {
  .rep-grid { grid-template-columns: 220px minmax(0, 1fr); }
  .rep-sources { display: none; }
}
@media (max-width: 900px) {
  .rep-grid { grid-template-columns: 1fr; }
}
</style>
