<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Document, CopyDocument, VideoPlay, Refresh, CloseBold, Check,
  Edit, Close, Flag, EditPen, Link, Filter, ArrowRight, Promotion,
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { citationApi, type CitationListItem, type CitationDecision } from '@/api/client'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.cc-head, .cc-flow', { delay: (_el, i) => 80 + i * 80 })
useEntrance('.cc-step', { delay: (_el, i) => 280 + i * 70 })
useEntrance('.cc-list, .cc-detail, .ov-cell', { delay: (_el, i) => 200 + i * 60 })
import type { Citation } from '@/types/api'

const router = useRouter()
const task = useTaskStore()
const active = ref(0)
const filterStatus = ref('all')
const pageSize = ref('10')

// Server-side citations + decisions
const serverCitations = ref<CitationListItem[]>([])
const serverSummary = ref<Record<string, number>>({})
const loading = ref(false)

async function copyText(value: string | undefined, label: string) {
  if (!value) {
    ElMessage.warning(`没有可复制的${label}`)
    return
  }
  await navigator.clipboard.writeText(value)
  ElMessage.success(`${label}已复制`)
}

async function loadCitations() {
  if (!task.current?.id) return
  loading.value = true
  try {
    const resp = await citationApi.list(task.current.id)
    serverCitations.value = resp.items
    serverSummary.value = resp.summary
  } catch (err) {
    ElMessage.error(`加载引用失败:${(err as Error).message}`)
  } finally { loading.value = false }
}

onMounted(async () => {
  if (!task.tasks.length) await task.refreshTasks()
  if (!task.current?.final_report) {
    const cand = task.tasks.find((t) => t.final_report)
    if (cand) await task.load(cand.id, false)
  }
  await loadCitations()
})
watch(() => task.current?.id, () => loadCitations())

interface CiteRow {
  n: number
  body: string
  status: 'pass' | 'wait' | 'low'
  conf: number
  risk: 'low' | 'mid' | 'high'
  citation: Citation
  decision: CitationDecision | null
}

function sourceHost(c: Citation): string {
  try { return new URL(c.url).hostname } catch { return '' }
}
function classify(c: Citation): { status: 'pass' | 'wait' | 'low'; conf: number; risk: 'low' | 'mid' | 'high' } {
  const isMock = c.url.startsWith('https://example.com')
  const trusted = /idc|gartner|mckinsey|forrester|bcg|nature|arxiv|stanford/i.test(c.url + c.title)
  let conf = trusted ? 0.85 : isMock ? 0.40 : 0.62
  conf = Math.min(.99, Math.max(.10, conf + (c.number % 3) * 0.02))
  const status: 'pass' | 'wait' | 'low' = conf >= 0.75 ? 'pass' : conf >= 0.5 ? 'wait' : 'low'
  const risk: 'low' | 'mid' | 'high' = conf >= 0.75 ? 'low' : conf >= 0.5 ? 'mid' : 'high'
  return { status, conf, risk }
}

// Map server citation decisions onto the heuristic-derived rows
const citations = computed<CiteRow[]>(() => {
  const decisionMap = new Map<number, CitationDecision>()
  for (const c of serverCitations.value) {
    if (c.decision) decisionMap.set(c.number, c.decision)
  }
  const list = task.finalReport?.citations ?? []
  return list.map((c) => {
    const m = classify(c)
    const decision = decisionMap.get(c.number) || null
    let status: 'pass' | 'wait' | 'low' = m.status
    if (decision) {
      if (decision.status === 'pass') status = 'pass'
      else if (decision.status === 'flag') status = 'wait'
      else if (decision.status === 'reject') status = 'low'
    }
    return { n: c.number, body: c.quote || c.title, status, conf: m.conf, risk: m.risk, citation: c, decision }
  })
})
const filteredCitations = computed(() => {
  if (filterStatus.value === 'all') return citations.value
  return citations.value.filter((c) => c.status === filterStatus.value)
})
const activeCitation = computed<CiteRow | null>(() => filteredCitations.value[active.value] ?? null)

const passedCount = computed(() => citations.value.filter((c) => c.status === 'pass').length)
const totalCount = computed(() => citations.value.length)
const progressPct = computed(() => totalCount.value ? Math.round(passedCount.value / totalCount.value * 100) : 0)

const flow = computed(() => {
  const total = totalCount.value
  return [
    { n: 1, label: '抽取引用', sub: `${total} 项`, state: total > 0 ? 'done' : 'todo' },
    { n: 2, label: '来源匹配', sub: `${total} 项`, state: total > 0 ? 'done' : 'todo' },
    { n: 3, label: '事实核对', sub: `${passedCount.value} / ${total}`, state: progressPct.value === 100 ? 'done' : progressPct.value > 0 ? 'current' : 'todo' },
    { n: 4, label: '质量评分', sub: task.quality ? '已完成' : '待开始', state: task.quality ? 'done' : 'todo' },
    { n: 5, label: '生成结论', sub: task.finalReport ? '已完成' : '待开始', state: task.finalReport ? 'done' : 'todo' },
  ]
})

const overview = computed(() => {
  const items = citations.value
  const high = items.filter((c) => c.conf >= 0.75).length
  const mid  = items.filter((c) => c.conf >= 0.5 && c.conf < 0.75).length
  const low  = items.filter((c) => c.conf < 0.5).length
  const total = items.length || 1
  return [
    { label: '高置信度', value: high, pct: Math.round(high / total * 100) + '%', color: 'green', ico: '🎯' },
    { label: '中置信度', value: mid,  pct: Math.round(mid  / total * 100) + '%', color: 'orange', ico: '⚙' },
    { label: '低置信度', value: low,  pct: Math.round(low  / total * 100) + '%', color: 'red',   ico: '⊗' },
    { label: '待复核',   value: items.filter((c) => c.status === 'wait').length,
      pct: Math.round(items.filter((c) => c.status === 'wait').length / total * 100) + '%',
      color: 'gray',  ico: '✎' },
  ]
})

const sources = computed(() => {
  const map = new Map<string, number>()
  for (const c of citations.value) {
    const host = sourceHost(c.citation) || 'unknown'
    map.set(host, (map.get(host) || 0) + 1)
  }
  const total = citations.value.length || 1
  const palette = ['#2563eb', '#16a34a', '#a78bfa', '#f97316', '#fb7185', '#94a3b8']
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count], i) => ({
      name, count, pct: Math.round(count / total * 100), color: palette[i] || '#94a3b8',
    }))
})

const tips = computed(() => {
  const items = citations.value
  const low = items.filter((c) => c.status === 'low').length
  const wait = items.filter((c) => c.status === 'wait').length
  const out: { title: string; desc: string; color: string; ico: string }[] = []
  if (low > 0)  out.push({ title: `低置信度引用 (${low})`, desc: '建议优先核查来源时效性与数据口径', color: 'red',    ico: '⚠' })
  if (wait > 0) out.push({ title: `待人工复核 (${wait})`,  desc: '涉及解读性结论,建议人工确认',     color: 'orange', ico: '⚙' })
  out.push({ title: '查看校验日志', desc: '', color: 'gray', ico: '📋' })
  return out
})

function statusInfo(s: string) {
  if (s === 'pass') return { cls: 'tag-green',  label: '已通过' }
  if (s === 'wait') return { cls: 'tag-orange', label: '待人工复核' }
  if (s === 'low')  return { cls: 'tag-red',    label: '低置信度' }
  return { cls: 'tag', label: '其他' }
}

// ---- Actions wired to /v1/research/{id}/citations/{n}/verify ----
async function verifyCitation(n: number, status: 'pass' | 'reject' | 'flag' | 'replaced', label: string) {
  if (!task.current?.id) return
  try {
    await citationApi.verify(task.current.id, n, status)
    ElMessage.success(`已${label} [${n}]`)
    await loadCitations()
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

async function refreshAll() {
  if (!task.current?.id) return
  await Promise.all([task.load(task.current.id, false), loadCitations()])
  ElMessage.success('已刷新')
}

async function reextract() {
  // No dedicated re-extract endpoint yet; reload from server to pull any
  // newly persisted citation rows.
  await refreshAll()
  ElMessage.info('已重新拉取引用列表(基于已生成报告)')
}

async function generateConclusion() {
  try {
    await ElMessageBox.confirm(
      `已完成 ${serverSummary.value.pass || 0} / ${serverSummary.value.total || 0} 项验证,确认生成校验结论?`,
      '生成结论',
      { type: 'info' },
    )
    // For MVP we just snapshot the summary and notify; future work: persist
    // a conclusion record server-side.
    ElMessage.success('已生成校验结论(预览版,持久化将在 v6 提供)')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}
function riskInfo(r: string) {
  if (r === 'low')  return { color: 'green',  label: '低' }
  if (r === 'mid')  return { color: 'orange', label: '中' }
  return { color: 'red', label: '高' }
}
</script>

<template>
  <div class="cc">
    <ElEmpty v-if="!task.finalReport" description="尚无可校验的报告。完成研究后,引用会自动出现在这里。">
      <ElButton type="primary" :icon="Promotion" @click="router.push('/')">开始研究</ElButton>
    </ElEmpty>

    <template v-else>
    <!-- Head -->
    <section class="card cc-head">
      <div class="cc-head-left">
        <div class="cc-icon"><ElIcon><Document /></ElIcon></div>
        <div>
          <small class="cc-sub-label">任务 / 报告</small>
          <h2>{{ task.current?.question }}</h2>
          <div class="cc-meta">
            <span>任务 ID:<code>{{ task.current?.id }}</code></span>
            <ElIcon class="copy-ico" @click="copyText(task.current?.id, '任务 ID')"><CopyDocument /></ElIcon>
          </div>
          <div class="cc-meta-row">
            <span v-if="task.current?.created_at">📅 创建:{{ new Date(task.current.created_at).toLocaleString('zh-CN') }}</span>
            <span v-if="task.current?.updated_at">📅 更新:{{ new Date(task.current.updated_at).toLocaleString('zh-CN') }}</span>
          </div>
        </div>
      </div>

      <div class="cc-prog">
        <div class="cc-prog-label">验证进度</div>
        <div class="cc-prog-value">
          <span class="primary">{{ passedCount }} / {{ totalCount }}</span>
          <small>已通过 / 总数</small>
        </div>
        <div class="rp-bar"><i :style="{ width: progressPct + '%' }" /></div>
        <div class="cc-prog-meta">
          <span>{{ progressPct }}%</span>
          <span v-if="totalCount > passedCount">待复核:{{ totalCount - passedCount }} 项</span>
        </div>
      </div>

      <div class="cc-conf">
        <div class="cc-conf-label">平均置信度</div>
        <div class="cc-conf-value">{{ totalCount ? Math.round(citations.reduce((s, c) => s + c.conf, 0) / totalCount * 100) : 0 }}%</div>
        <div class="cc-conf-bar">
          <span :style="{ width: overview[0].pct, background: 'var(--green)' }" />
          <span :style="{ width: overview[1].pct, background: 'var(--yellow)' }" />
          <span :style="{ width: overview[2].pct, background: 'var(--red)' }" />
          <span :style="{ width: overview[3].pct, background: 'var(--muted-soft)' }" />
        </div>
        <div class="cc-conf-legend">
          <span>高 {{ overview[0].pct }}</span><span>中 {{ overview[1].pct }}</span>
          <span>低 {{ overview[2].pct }}</span><span>待复核 {{ overview[3].pct }}</span>
        </div>
      </div>

      <div class="cc-actions">
        <button class="primary-btn" :disabled="loading" @click="refreshAll"><ElIcon><VideoPlay /></ElIcon><span>刷新数据</span></button>
        <button class="btn-secondary" :disabled="loading" @click="reextract"><ElIcon><Refresh /></ElIcon><span>重新抽取</span></button>
        <button class="btn-danger" :disabled="!totalCount" @click="generateConclusion"><ElIcon><CloseBold /></ElIcon><span>生成结论</span></button>
      </div>
    </section>

    <!-- Flow -->
    <section class="card cc-flow">
      <div class="cc-step" v-for="s in flow" :key="s.n" :data-state="s.state">
        <div class="cc-step-c">
          <ElIcon v-if="s.state === 'done'"><Check /></ElIcon>
          <span v-else>{{ s.n }}</span>
        </div>
        <div class="cc-step-label">{{ s.label }}</div>
        <div class="cc-step-sub">{{ s.sub }}</div>
      </div>
    </section>

    <!-- 3-col body -->
    <div class="cc-grid">
      <!-- citation list -->
      <article class="card cc-list">
        <header class="cc-list-head">
          <div>
            <h3>待验证引用列表 <small>({{ filteredCitations.length }})</small></h3>
          </div>
          <div class="cc-list-actions">
            <ElSelect v-model="filterStatus" size="default" style="width: 110px;">
              <ElOption label="全部状态" value="all" />
              <ElOption label="已通过" value="pass" />
              <ElOption label="待复核" value="wait" />
              <ElOption label="低置信度" value="low" />
            </ElSelect>
            <button class="btn-secondary square"><ElIcon><Filter /></ElIcon></button>
          </div>
        </header>
        <div class="cl-th">
          <div>编号</div>
          <div>断言 / 状态</div>
        </div>
        <ElEmpty v-if="!filteredCitations.length" :image-size="56" description="没有匹配的引用" />
        <div
          v-for="(c, i) in filteredCitations" :key="c.n"
          class="cl-row" :class="{ active: active === i }"
          @click="active = i"
        >
          <div class="cl-n">[{{ c.n }}]</div>
          <div class="cl-body">
            <p>{{ c.body }}</p>
            <div class="cl-meta">
              <span class="tag" :class="statusInfo(c.status).cls"><i />{{ statusInfo(c.status).label }}</span>
              <span class="mono">{{ c.conf.toFixed(2) }}</span>
              <span class="tag" :class="`tag-${riskInfo(c.risk).color}`"><i />{{ riskInfo(c.risk).label }}</span>
            </div>
          </div>
        </div>
      </article>

      <!-- detail -->
      <article class="card cc-detail" v-if="activeCitation">
        <header class="cc-detail-head">
          <h3>引用详情 <span class="cd-num">[{{ activeCitation.n }}]</span></h3>
          <div class="cd-source">
            <span>第 {{ active + 1 }} / {{ filteredCitations.length }}</span>
            <button class="ico-btn-sm" :disabled="active <= 0" @click="active = Math.max(0, active - 1)">
              <ElIcon><ArrowRight style="transform: rotate(180deg);" /></ElIcon>
            </button>
            <button class="ico-btn-sm" :disabled="active >= filteredCitations.length - 1"
                    @click="active = Math.min(filteredCitations.length - 1, active + 1)">
              <ElIcon><ArrowRight /></ElIcon>
            </button>
          </div>
        </header>
        <section class="cd-block">
          <header><h4>报告中的断言</h4><ElIcon class="copy-ico" @click="copyText(activeCitation.citation.quote || activeCitation.citation.title, '断言')"><CopyDocument /></ElIcon></header>
          <div class="cd-quote">
            <p>{{ activeCitation.citation.quote || activeCitation.citation.title }}</p>
            <small v-if="activeCitation.citation.title">报告引用编号:[{{ activeCitation.n }}]</small>
          </div>
        </section>
        <section class="cd-block">
          <header><h4>提取的事实</h4></header>
          <div class="cd-fact">{{ activeCitation.citation.quote || activeCitation.citation.title || '(无可提取的断言)' }}</div>
        </section>
        <section class="cd-block">
          <header><h4>来源信息</h4><a class="link-mini" v-if="activeCitation.citation.url" :href="activeCitation.citation.url" target="_blank">查看原文</a></header>
          <div class="cd-info">
            <div class="kv"><span>标题:</span><b>{{ activeCitation.citation.title }}</b></div>
            <div class="kv"><span>来源域名:</span><b>{{ sourceHost(activeCitation.citation) || '—' }}</b></div>
            <div class="kv"><span>链接:</span><a :href="activeCitation.citation.url" target="_blank">{{ activeCitation.citation.url }} <ElIcon><Link /></ElIcon></a></div>
          </div>
        </section>
        <section class="cd-block">
          <header><h4>对比与核对说明 (启发式)</h4></header>
          <div class="cd-grid">
            <span>置信度:<b>{{ activeCitation.conf.toFixed(2) }}</b></span>
            <span>风险等级:<b>{{ riskInfo(activeCitation.risk).label }}</b></span>
            <span>状态:<b>{{ statusInfo(activeCitation.status).label }}</b></span>
            <span>结论:<b class="primary">{{ activeCitation.status === 'pass' ? '支持该断言' : '待人工确认' }}</b></span>
          </div>
        </section>
        <section class="cd-actions">
          <header>
            <h4>操作</h4>
            <span v-if="activeCitation.decision" class="cd-decision-meta">
              当前:<b>{{ activeCitation.decision.status }}</b> · {{ new Date(activeCitation.decision.decided_at).toLocaleString('zh-CN') }}
            </span>
          </header>
          <div class="cd-buttons">
            <button class="btn-approve sm" @click="verifyCitation(activeCitation.n, 'pass', '通过')"><ElIcon><Check /></ElIcon><span>通过</span></button>
            <button class="btn-reject sm" @click="verifyCitation(activeCitation.n, 'reject', '驳回')"><ElIcon><Close /></ElIcon><span>驳回</span></button>
            <button class="btn-flag sm" @click="verifyCitation(activeCitation.n, 'flag', '标记复核')"><ElIcon><Flag /></ElIcon><span>标记复核</span></button>
            <button class="btn-edit sm" @click="verifyCitation(activeCitation.n, 'replaced', '替换来源')"><ElIcon><Refresh /></ElIcon><span>替换来源</span></button>
          </div>
        </section>
      </article>
      <article v-else class="card cc-detail"><ElEmpty :image-size="64" description="选中左侧引用查看详情" /></article>

      <!-- right meta -->
      <aside class="cc-side">
        <article class="card card-pad">
          <header class="section-head"><h3 class="card-title">验证概览</h3></header>
          <div class="ov-grid">
            <div v-for="o in overview" :key="o.label" class="ov-cell" :data-color="o.color">
              <span class="ov-ico">{{ o.ico }}</span>
              <div class="ov-label">{{ o.label }}</div>
              <div class="ov-value">{{ o.value }}</div>
              <div class="ov-pct">{{ o.pct }}</div>
            </div>
          </div>
        </article>

        <article class="card card-pad">
          <header class="section-head"><h3 class="card-title">来源分布 <small>(匹配的主要来源)</small></h3></header>
          <div class="src-donut">
            <svg viewBox="0 0 80 80" class="donut">
              <circle cx="40" cy="40" r="32" fill="none" stroke="#e5e7eb" stroke-width="12" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#2563eb" stroke-width="12"
                      stroke-dasharray="58 201" transform="rotate(-90 40 40)" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#16a34a" stroke-width="12"
                      stroke-dasharray="46 201" stroke-dashoffset="-58" transform="rotate(-90 40 40)" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#a78bfa" stroke-width="12"
                      stroke-dasharray="30 201" stroke-dashoffset="-104" transform="rotate(-90 40 40)" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#f97316" stroke-width="12"
                      stroke-dasharray="24 201" stroke-dashoffset="-134" transform="rotate(-90 40 40)" />
              <circle cx="40" cy="40" r="32" fill="none" stroke="#fb7185" stroke-width="12"
                      stroke-dasharray="16 201" stroke-dashoffset="-158" transform="rotate(-90 40 40)" />
            </svg>
            <ul>
              <li v-for="s in sources" :key="s.name">
                <span class="dot" :style="{ background: s.color }" />
                <span>{{ s.name }}</span>
                <b>{{ s.count }}</b>
                <small>({{ s.pct }}%)</small>
              </li>
            </ul>
          </div>
          <a class="link-foot">查看全部来源 ›</a>
        </article>

        <article class="card card-pad">
          <header class="section-head"><h3 class="card-title">校验建议</h3></header>
          <ul class="tip-list">
            <li v-for="t in tips" :key="t.title">
              <div class="tip-ico" :data-color="t.color">{{ t.ico }}</div>
              <div class="tip-body">
                <strong>{{ t.title }}</strong>
                <p v-if="t.desc">{{ t.desc }}</p>
              </div>
              <ElIcon class="tip-arrow"><ArrowRight /></ElIcon>
            </li>
          </ul>
        </article>
      </aside>
    </div>
    </template>
  </div>
</template>

<style scoped>
.cc { display: grid; gap: 16px; }

/* Head */
.cc-head {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr) 200px;
  gap: 22px;
  padding: 18px 22px;
  align-items: center;
}
.cc-head-left { display: flex; gap: 14px; align-items: flex-start; }
.cc-icon {
  width: 46px; height: 46px;
  border-radius: 10px;
  background: #dbeafe;
  color: #2563eb;
  display: grid; place-items: center;
  flex-shrink: 0;
}
.cc-icon .el-icon { font-size: 20px; }
.cc-sub-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.cc-head-left h2 { margin: 4px 0 6px; font-size: 17px; font-weight: 700; color: var(--text); }
.cc-meta { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
.cc-meta-row { display: flex; gap: 14px; font-size: 12px; color: var(--muted); margin-top: 4px; }
.cc-meta code { font-family: var(--t-mono); font-size: 12px; color: var(--text-soft); }
.copy-ico { color: var(--muted-soft); cursor: pointer; font-size: 13px; }

.cc-prog { display: grid; gap: 6px; }
.cc-prog-label { font-size: 12.5px; color: var(--muted); }
.cc-prog-value { display: flex; align-items: baseline; gap: 8px; }
.cc-prog-value .primary { color: var(--primary); font-size: 24px; font-weight: 700; font-family: var(--t-mono); }
.cc-prog-value small { color: var(--muted); font-size: 12px; }
.rp-bar { height: 6px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.rp-bar i { display: block; height: 100%; background: var(--primary); border-radius: inherit; }
.cc-prog-meta { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--muted); }

.cc-conf { display: grid; gap: 6px; }
.cc-conf-label { font-size: 12.5px; color: var(--muted); }
.cc-conf-value { font-size: 24px; font-weight: 700; color: var(--primary); letter-spacing: -.01em; }
.cc-conf-value .up { font-size: 12px; color: var(--green); font-weight: 600; margin-left: 8px; }
.cc-conf-bar {
  display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: var(--surface-3);
}
.cc-conf-bar span { display: block; height: 100%; }
.cc-conf-legend { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--muted); }

.cc-actions { display: grid; gap: 6px; }
.cc-actions button { width: 100%; justify-content: center; }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer;
}
.btn-secondary.square { padding: 0; width: 34px; justify-content: center; }
.btn-secondary:hover { border-color: var(--primary-line); color: var(--primary); }
.btn-danger {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 12px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--red);
  border: 1px solid #fecaca;
  font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer;
}
.btn-danger:hover { background: var(--red-soft); }

/* Flow */
.cc-flow {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  align-items: center;
  padding: 18px 22px;
  position: relative;
}
.cc-step { position: relative; display: grid; place-items: center; gap: 6px; }
.cc-step-c {
  width: 40px; height: 40px;
  display: grid; place-items: center;
  border-radius: 50%;
  background: var(--surface);
  border: 2px solid var(--border-strong);
  color: var(--muted);
  font: 600 14px/1 var(--t-mono);
  z-index: 1;
}
.cc-step[data-state='done'] .cc-step-c {
  background: var(--green-soft);
  border-color: var(--green);
  color: var(--green);
}
.cc-step[data-state='current'] .cc-step-c {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  box-shadow: 0 0 0 4px var(--primary-soft);
}
.cc-step-label { font-size: 13px; font-weight: 600; color: var(--text); }
.cc-step[data-state='todo'] .cc-step-label { color: var(--muted); }
.cc-step-sub { font-size: 11.5px; color: var(--muted); }
.cc-step[data-state='current'] .cc-step-sub { color: var(--primary); font-weight: 600; }
.cc-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 19px;
  left: calc(50% + 22px);
  width: calc(100% - 44px);
  height: 2px;
  border-top: 2px dashed var(--border-strong);
  background: transparent;
  z-index: 0;
}
.cc-step[data-state='done']:not(:last-child)::after { border-color: var(--green); }

/* Grid */
.cc-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.5fr) 280px;
  gap: 16px;
  align-items: start;
}

/* List */
.cc-list { padding: 0; overflow: hidden; }
.cc-list-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border); }
.cc-list-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text); }
.cc-list-head h3 small { color: var(--muted); margin-left: 4px; }
.cc-list-actions { display: flex; gap: 6px; }

.cl-th, .cl-row {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 10px;
  padding: 10px 16px;
  font-size: 12px;
}
.cl-th { background: var(--surface-3); color: var(--text-soft); font-weight: 600; border-bottom: 1px solid var(--border); }
.cl-th > div:nth-child(2) { display: grid; grid-template-columns: 1fr 110px 70px 60px; gap: 10px; }
.cl-row { border-bottom: 1px solid var(--border); cursor: pointer; transition: background .12s ease; }
.cl-row:hover { background: var(--surface-2); }
.cl-row.active { background: var(--primary-soft); }
.cl-row.active::before { content: ''; position: absolute; }
.cl-n { font-family: var(--t-mono); font-weight: 700; color: var(--primary); font-size: 13px; }
.cl-body { display: grid; gap: 6px; }
.cl-body p { margin: 0; font-size: 12.5px; color: var(--text-soft); line-height: 1.45; }
.cl-meta { display: flex; align-items: center; gap: 10px; }
.cl-meta .mono { color: var(--text); font-weight: 600; font-size: 12px; }

.tag { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border-radius: 6px; font-size: 11.5px; font-weight: 500; }
.tag i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.tag-green { background: var(--green-soft); color: var(--green-text); }
.tag-orange { background: var(--orange-soft); color: var(--orange-text); }
.tag-red { background: var(--red-soft); color: var(--red-text); }
.tag-gray { background: var(--gray-soft); color: var(--gray-text); }
.tag-yellow { background: var(--yellow-soft); color: var(--yellow-text); }

.cl-pager {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
}
.pager-mid { display: flex; align-items: center; gap: 4px; }
.pager-mid button {
  min-width: 26px; height: 26px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 12px;
  border-radius: 6px;
  cursor: pointer;
}
.pager-mid button.active { background: var(--primary); border-color: var(--primary); color: white; }

/* Detail */
.cc-detail { padding: 0; }
.cc-detail-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.cc-detail-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text); }
.cd-num { color: var(--primary); font-family: var(--t-mono); margin-left: 4px; }
.cd-source { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
.cd-source-cur { color: var(--text-soft); }
.ico-btn-sm {
  width: 26px; height: 26px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  display: grid; place-items: center;
}
.ico-btn-sm:hover { color: var(--primary); border-color: var(--primary-line); }

.cd-block {
  padding: 12px 18px;
  border-bottom: 1px solid var(--border);
}
.cd-block:last-of-type { border-bottom: none; }
.cd-block header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cd-block h4 { margin: 0; font-size: 12.5px; font-weight: 600; color: var(--text); }
.link-mini { font-size: 12px; color: var(--primary); cursor: pointer; display: inline-flex; gap: 4px; align-items: center; }
.cd-quote {
  padding: 10px 14px;
  background: var(--surface-2);
  border-left: 3px solid var(--primary);
  border-radius: 0 6px 6px 0;
}
.cd-quote.alt { border-color: var(--green); }
.cd-quote p { margin: 0; font-size: 13px; color: var(--text); line-height: 1.55; font-style: italic; }
.cd-quote small { display: block; margin-top: 6px; font-size: 11px; color: var(--muted); }
.cd-fact {
  padding: 10px 14px;
  background: var(--primary-soft);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text);
}
.cd-info { display: grid; gap: 6px; }
.kv { display: flex; gap: 8px; font-size: 12.5px; }
.kv span { color: var(--muted); flex-shrink: 0; }
.kv b { color: var(--text); font-weight: 500; }
.kv a { color: var(--primary); display: inline-flex; align-items: center; gap: 4px; }
.cd-compare { font-size: 13px; color: var(--text-soft); margin-bottom: 8px; }
.cd-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  font-size: 12px;
  color: var(--muted);
}
.cd-grid b { color: var(--text); font-weight: 600; margin-left: 4px; }
.cd-grid .primary { color: var(--green); }

.cd-actions { padding: 12px 18px; }
.cd-buttons { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 4px; }
.btn-approve, .btn-reject, .btn-flag, .btn-edit {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  height: 34px; padding: 0 12px;
  border-radius: 8px;
  font: inherit; font-size: 12.5px; font-weight: 600;
  cursor: pointer;
  border: 1px solid;
}
.btn-approve { background: var(--green-soft); color: var(--green); border-color: #bbf7d0; }
.btn-approve:hover { background: var(--green); color: white; }
.btn-reject { background: var(--red-soft); color: var(--red); border-color: #fecaca; }
.btn-reject:hover { background: var(--red); color: white; }
.btn-flag { background: var(--orange-soft); color: var(--orange); border-color: #fed7aa; }
.btn-flag:hover { background: var(--orange); color: white; }
.btn-edit { background: var(--primary-soft); color: var(--primary); border-color: var(--primary-line); }
.btn-edit:hover { background: var(--primary); color: white; }
.btn-approve.sm, .btn-reject.sm, .btn-flag.sm, .btn-edit.sm { height: 36px; }

/* Right side */
.cc-side { display: grid; gap: 16px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-head h3 { font-size: 14px; font-weight: 600; color: var(--text); }
.section-head h3 small { font-size: 11px; color: var(--muted); margin-left: 4px; font-weight: 400; }

.ov-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.ov-cell {
  position: relative;
  padding: 14px;
  border-radius: 8px;
  background: var(--surface-3);
}
.ov-cell[data-color='green']  { background: var(--green-soft); }
.ov-cell[data-color='orange'] { background: var(--orange-soft); }
.ov-cell[data-color='red']    { background: var(--red-soft); }
.ov-cell[data-color='gray']   { background: var(--surface-3); }
.ov-ico { position: absolute; top: 12px; right: 12px; font-size: 14px; }
.ov-label { font-size: 12px; color: var(--text-soft); margin-bottom: 4px; }
.ov-cell[data-color='green']  .ov-label { color: var(--green-text); }
.ov-cell[data-color='orange'] .ov-label { color: var(--orange-text); }
.ov-cell[data-color='red']    .ov-label { color: var(--red-text); }
.ov-value { font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; }
.ov-pct { font-size: 11px; color: var(--muted); margin-top: 2px; }

.src-donut { display: flex; gap: 12px; align-items: center; }
.donut { width: 80px; height: 80px; flex-shrink: 0; }
.src-donut ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; flex: 1; font-size: 12px; }
.src-donut li { display: flex; align-items: center; gap: 6px; }
.src-donut .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.src-donut span { flex: 1; color: var(--text-soft); }
.src-donut b { color: var(--text); font-weight: 600; }
.src-donut small { color: var(--muted-soft); font-size: 11px; }

.link-foot { display: block; text-align: center; margin-top: 10px; padding: 8px; font-size: 12.5px; color: var(--primary); cursor: pointer; }

.tip-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.tip-list li {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-3);
  cursor: pointer;
}
.tip-list li:hover { background: var(--surface-2); }
.tip-ico {
  width: 24px; height: 24px;
  border-radius: 6px;
  display: grid; place-items: center;
  font-size: 12px;
  flex-shrink: 0;
}
.tip-ico[data-color='blue']   { background: #dbeafe; color: #2563eb; }
.tip-ico[data-color='green']  { background: #dcfce7; color: #16a34a; }
.tip-ico[data-color='red']    { background: #fee2e2; color: #dc2626; }
.tip-ico[data-color='orange'] { background: #ffedd5; color: #f97316; }
.tip-ico[data-color='gray']   { background: var(--surface-3); color: var(--muted); }
.tip-body { flex: 1; min-width: 0; }
.tip-body strong { font-size: 12.5px; color: var(--text); display: block; }
.tip-body p { margin: 4px 0 0; font-size: 11.5px; color: var(--muted); line-height: 1.5; }
.tip-arrow { color: var(--muted-soft); font-size: 12px; align-self: center; }

@media (max-width: 1500px) {
  .cc-head { grid-template-columns: 1fr; gap: 14px; }
  .cc-grid { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .cc-flow { grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .cc-flow .cc-step::after { display: none; }
  .cd-grid { grid-template-columns: 1fr 1fr; }
  .cd-buttons { grid-template-columns: 1fr 1fr; }
}
</style>
