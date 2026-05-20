<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Refresh, Download, Warning, ArrowRight, More,
} from '@element-plus/icons-vue'
import EChart from '@/components/charts/EChart.vue'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { useEntrance, runCountUp } from '@/composables/useAnime'
import { nextTick } from 'vue'

useEntrance('.cost-kpi-grid .card')
useEntrance('.chart-2col article, .task-table, .cost-side > article', { delay: (_el, i) => 200 + i * 60 })
import { costApi, type CostByModel, type CostByNode, type CostSummary, type CostTrend, type CostTaskRow, type CostTip } from '@/api/client'

const task = useTaskStore()
const session = useSessionStore()

const range = ref('this-month')

// Real API state
const summary = ref<CostSummary | null>(null)
const trendData = ref<CostTrend | null>(null)
const byModel = ref<CostByModel | null>(null)
const byNode = ref<CostByNode | null>(null)
const taskRowsApi = ref<CostTaskRow[]>([])
const tipsApi = ref<CostTip[]>([])
const loading = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [s, t, m, n, ts, tp] = await Promise.all([
      costApi.summary(range.value),
      costApi.trend(range.value, trendMode.value),
      costApi.byModel(range.value),
      costApi.byNode(range.value),
      costApi.tasks(range.value, 20),
      costApi.tips(),
    ])
    summary.value = s; trendData.value = t; byModel.value = m; byNode.value = n
    taskRowsApi.value = ts.items; tipsApi.value = tp.items
  } catch (err) {
    console.warn('[cost] load failed', err)
  } finally { loading.value = false }
}
onMounted(async () => {
  await task.refreshTasks(); await loadAll()
  await nextTick(); runCountUp('.cost-kpi-number')
})
watch(range, async () => { await loadAll(); await nextTick(); runCountUp('.cost-kpi-number') })
const project = ref('all')
const model = ref('all')
const center = ref('all')
const trendMode = ref<'day' | 'week'>('day')
watch(trendMode, () => costApi.trend(range.value, trendMode.value).then((t) => trendData.value = t))

const totalCost = computed(() => task.tasks.reduce((s, t) => s + (t.cost_usd || 0), 0))
const taskCount = computed(() => task.tasks.length)
const activeCount = computed(() => task.tasks.filter((t) =>
  ['planning', 'researching', 'writing', 'quality_gate', 'waiting_review', 'created'].includes(t.status),
).length)
const avgCost = computed(() => taskCount.value ? totalCost.value / taskCount.value : 0)
const budget = computed(() => session.budgetUsd || 50)
const budgetPct = computed(() => Math.min(100, totalCost.value / Math.max(0.01, budget.value) * 100))

const totalTokensIn = computed(() => {
  let n = 0
  for (const t of task.tasks) {
    for (const ev of (t.final_report ? [] : []) ) n += 0
  }
  return n
})

const apiTotalCost = computed(() => summary.value?.total_cost_usd ?? 0)
const apiBudgetPct = computed(() => Math.min(100, apiTotalCost.value / Math.max(0.01, budget.value) * 100))

const kpis = computed(() => [
  { label: '本月总成本',     value: '$ ' + apiTotalCost.value.toFixed(4),       unit: 'USD',    delta: `${summary.value?.task_count ?? 0} 个任务` },
  { label: '预算使用率',     value: apiBudgetPct.value.toFixed(1) + '%',         unit: '',       delta: `已用 $${apiTotalCost.value.toFixed(2)} / 预算 $${budget.value.toFixed(2)}` },
  { label: 'Token 消耗',     value: ((summary.value?.total_tokens ?? 0) / 1_000_000).toFixed(2) + 'M', unit: 'Tokens', delta: `输入 ${((summary.value?.input_tokens ?? 0) / 1_000_000).toFixed(2)}M · 输出 ${((summary.value?.output_tokens ?? 0) / 1_000_000).toFixed(2)}M` },
  { label: '单任务平均成本', value: '$ ' + (summary.value?.avg_cost_per_task ?? 0).toFixed(4), unit: 'USD', delta: '由实际任务平均' },
  { label: '活跃任务数',     value: String(activeCount.value),                   unit: '个',     delta: '当前进行中' },
  { label: '引用总数',       value: String(task.tasks.reduce((s, t) => s + (t.final_report?.citations?.length ?? 0), 0)), unit: '条', delta: '来自已完成报告' },
])

const palette = ['#2563eb', '#16a34a', '#f97316', '#facc15', '#7c3aed', '#94a3b8', '#fb7185']

// Trend line chart from API
const trendOption = computed(() => ({
  grid: { left: 32, right: 12, top: 30, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trendData.value?.labels ?? [],
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } },
    axisLine: { show: false }, axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
  },
  legend: { data: ['总成本 (USD)'], textStyle: { color: '#64748b', fontSize: 11 }, top: 0, left: 0, itemWidth: 10, itemHeight: 6 },
  series: [{
    name: '总成本 (USD)', type: 'line', smooth: true,
    symbol: 'circle', symbolSize: 5,
    data: trendData.value?.values ?? [],
    itemStyle: { color: '#2563eb' },
    lineStyle: { width: 2, color: '#2563eb' },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(37,99,235,.18)' }, { offset: 1, color: 'rgba(37,99,235,0)' }] } },
  }],
}))

const modelDistOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { show: false },
  series: [{
    type: 'pie',
    radius: ['62%', '85%'],
    label: { show: false }, labelLine: { show: false },
    data: (byModel.value?.items ?? []).map((it, i) => ({
      value: it.cost_usd,
      name: it.model || 'unknown',
      itemStyle: { color: palette[i % palette.length] },
    })),
  }],
}))

const nodeBarOption = computed(() => {
  const items = byNode.value?.items ?? []
  return {
    grid: { left: 130, right: 60, top: 10, bottom: 24 },
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
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    series: [{
      type: 'bar', barWidth: 14,
      data: items.map((i) => i.cost_usd),
      itemStyle: { color: '#2563eb', borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: '#0f172a', fontSize: 11, formatter: (p: any) => '$' + Number(p.value).toFixed(4) },
    }],
  }
})

// Token bars — use the same time buckets as trend; values are scaled from cost*1000 as a proxy
const tokenOption = computed(() => {
  const labels = trendData.value?.labels ?? []
  const totals = trendData.value?.values ?? []
  // Distribute total cost into in/out tokens using overall in/out ratio
  const inTok = summary.value?.input_tokens ?? 0
  const outTok = summary.value?.output_tokens ?? 0
  const sumCost = totals.reduce((s, v) => s + v, 0) || 1
  const inSeries = totals.map((v) => Math.round((v / sumCost) * inTok))
  const outSeries = totals.map((v) => Math.round((v / sumCost) * outTok))
  return {
    grid: { left: 36, right: 12, top: 28, bottom: 24 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['输入 Tokens', '输出 Tokens'], top: 0, left: 0, itemWidth: 10, itemHeight: 6 },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: (v: number) => v >= 1000 ? `${v / 1000}K` : v } },
    series: [
      { name: '输入 Tokens', type: 'bar', stack: 'tok', barWidth: 12, data: inSeries,  itemStyle: { color: '#2563eb', borderRadius: [3, 3, 0, 0] } },
      { name: '输出 Tokens', type: 'bar', stack: 'tok', barWidth: 12, data: outSeries, itemStyle: { color: '#16a34a' } },
    ],
  }
})

// Cumulative line — running total of trend values
const cumOption = computed(() => {
  const labels = trendData.value?.labels ?? []
  const values = trendData.value?.values ?? []
  const cum: number[] = []
  let running = 0
  for (const v of values) { running += v; cum.push(Number(running.toFixed(6))) }
  const len = labels.length || 1
  const step = budget.value / len
  const budgetLine = labels.map((_, i) => Number(((i + 1) * step).toFixed(2)))
  return {
    grid: { left: 36, right: 16, top: 28, bottom: 24 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['累计成本 (USD)', '预算 (USD)'], top: 0, left: 0, itemWidth: 14, itemHeight: 6 },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11 } },
    series: [
      { name: '累计成本 (USD)', type: 'line', smooth: true, data: cum,
        itemStyle: { color: '#2563eb' }, lineStyle: { width: 2 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(37,99,235,.15)' }, { offset: 1, color: 'rgba(37,99,235,0)' }] } } },
      { name: '预算 (USD)', type: 'line', symbol: 'none', data: budgetLine, lineStyle: { color: '#94a3b8', type: 'dashed', width: 2 }, itemStyle: { color: '#94a3b8' } },
    ],
  }
})

const taskRows = computed(() =>
  taskRowsApi.value.map((r) => ({
    name: r.task_name,
    stage: r.node || '—',
    model: r.model || '—',
    calls: r.calls,
    tokens: `${r.input_tokens.toLocaleString()} / ${r.output_tokens.toLocaleString()}`,
    cost: '$ ' + r.cost_usd.toFixed(4),
    pct: r.pct.toFixed(1) + '%',
    time: r.updated_at ? new Date(r.updated_at).toLocaleString('zh-CN') : '—',
  })),
)

const tips = computed(() =>
  tipsApi.value.map((t) => ({ title: t.title, desc: t.desc, icon: t.ico, color: t.color })),
)

const modelShare = computed(() =>
  (byModel.value?.items ?? []).map((it, i) => ({
    name: it.model || 'unknown',
    pct: it.pct,
    color: palette[i % palette.length],
  })),
)
</script>

<template>
  <div class="cost">
    <!-- Filter row -->
    <section class="cost-filters card">
      <div class="filter-field">
        <span class="filter-label">时间范围</span>
        <ElSelect v-model="range" size="default" style="width: 220px;">
          <ElOption label="本月 (2025-05-01 ~ 2025-05-31)" value="this-month" />
          <ElOption label="上月" value="last-month" />
          <ElOption label="近 7 天" value="7d" />
          <ElOption label="近 30 天" value="30d" />
        </ElSelect>
      </div>
      <div class="filter-field">
        <span class="filter-label">项目</span>
        <ElSelect v-model="project" size="default" style="width: 130px;">
          <ElOption label="全部项目" value="all" />
        </ElSelect>
      </div>
      <div class="filter-field">
        <span class="filter-label">模型</span>
        <ElSelect v-model="model" size="default" style="width: 130px;">
          <ElOption label="全部模型" value="all" />
        </ElSelect>
      </div>
      <div class="filter-field">
        <span class="filter-label">成本中心</span>
        <ElSelect v-model="center" size="default" style="width: 110px;">
          <ElOption label="全部" value="all" />
        </ElSelect>
      </div>
      <div class="filter-grow"></div>
      <button class="btn-secondary"><ElIcon><Refresh /></ElIcon><span>刷新</span></button>
      <button class="primary-btn"><ElIcon><Download /></ElIcon><span>导出报表</span></button>
    </section>

    <!-- KPI grid -->
    <section class="cost-kpi-grid">
      <div v-for="(k, i) in kpis" :key="i" class="card kpi-tile">
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-value-row">
          <span class="kpi-value">{{ k.value }}</span>
          <span class="kpi-unit">{{ k.unit }}</span>
        </div>
        <div class="kpi-delta">{{ k.delta }}</div>
      </div>
    </section>

    <ElAlert v-if="summary && summary.task_count === 0" type="info" :closable="false" show-icon class="demo-banner">
      <template #title>暂无任务数据</template>
      <span>在「研究台」启动任务后,此页面将基于真实 token 用量自动聚合 KPI、趋势、模型/节点分布。</span>
    </ElAlert>

    <!-- Layout: main grid + right -->
    <div class="cost-grid">
      <div class="cost-main">
        <article v-if="apiBudgetPct >= 80" class="card budget-alert">
          <div class="ba-ico"><ElIcon color="#f97316"><Warning /></ElIcon></div>
          <div class="ba-body">
            <strong>预算守护提醒</strong>
            <p>当前使用率 {{ apiBudgetPct.toFixed(0) }}%,接近预算上限,请关注并采取优化措施。</p>
          </div>
          <a class="ba-link">查看详情 <ElIcon><ArrowRight /></ElIcon></a>
        </article>

        <!-- 2-col charts -->
        <div class="chart-2col">
          <article class="card card-pad">
            <header class="chart-head">
              <h3>成本趋势 (按天)</h3>
              <div class="seg">
                <button :class="{ active: trendMode === 'day' }" @click="trendMode = 'day'">按天</button>
                <button :class="{ active: trendMode === 'week' }" @click="trendMode = 'week'">按周</button>
              </div>
            </header>
            <EChart :option="trendOption" height="200px" />
          </article>

          <article class="card card-pad">
            <header class="chart-head"><h3>模型成本分布</h3></header>
            <div class="donut-block">
              <EChart :option="modelDistOption" height="180px" />
              <div class="donut-center"><span class="dc-val">$12.48</span><span class="dc-lbl">总成本 (USD)</span></div>
            </div>
            <ElEmpty v-if="!byModel?.items.length" :image-size="48" description="暂无模型用量" />
            <ul v-else class="donut-list">
              <li v-for="(m, i) in byModel.items" :key="m.model + i">
                <span class="ld" :style="{ background: palette[i % palette.length] }" />
                {{ m.model || 'unknown' }}
                <b>${{ m.cost_usd.toFixed(4) }}</b>
                <small>({{ m.pct.toFixed(1) }}%)</small>
              </li>
            </ul>
          </article>

          <article class="card card-pad" style="grid-column: span 2;">
            <header class="chart-head"><h3>节点成本排行 (Top 6)</h3><small class="chart-unit">USD</small></header>
            <EChart :option="nodeBarOption" height="200px" />
          </article>

          <article class="card card-pad">
            <header class="chart-head"><h3>输入 / 输出 Token 趋势</h3></header>
            <EChart :option="tokenOption" height="220px" />
          </article>

          <article class="card card-pad">
            <header class="chart-head"><h3>累计成本趋势</h3></header>
            <EChart :option="cumOption" height="220px" />
          </article>
        </div>

        <!-- Task cost table -->
        <article class="card task-table">
          <header class="chart-head" style="padding: 16px 22px; margin: 0;">
            <h3>任务成本明细</h3>
          </header>
          <div class="th-row">
            <div>任务名称</div>
            <div>阶段 / 节点</div>
            <div>模型</div>
            <div>调用次数</div>
            <div>Tokens (输入 / 输出)</div>
            <div>成本 (USD)</div>
            <div>占比</div>
            <div>更新时间</div>
          </div>
          <div v-for="(r, i) in taskRows" :key="i" class="td-row">
            <div class="td-name">
              <span class="td-dot" :data-color="['blue','green','orange','purple','pink'][i % 5]" />
              <span>{{ r.name }}</span>
            </div>
            <div>{{ r.stage }}</div>
            <div>{{ r.model }}</div>
            <div>{{ r.calls }}</div>
            <div class="mono">{{ r.tokens }}</div>
            <div class="mono" style="font-weight: 600;">{{ r.cost }}</div>
            <div>{{ r.pct }}</div>
            <div class="td-time">{{ r.time }}</div>
          </div>
          <div class="task-foot">
            <span>查看全部任务明细 (8)</span>
            <button class="btn-secondary"><ElIcon><Download /></ElIcon><span>导出明细</span></button>
          </div>
        </article>
      </div>

      <!-- Right column -->
      <div class="cost-side">
        <article class="card card-pad">
          <header class="chart-head"><h3>成本优化建议</h3></header>
          <ul class="tip-list">
            <li v-for="(t, i) in tips" :key="i">
              <div class="tip-ico" :data-color="['blue','green','purple'][i % 3]">{{ t.icon }}</div>
              <div class="tip-body">
                <strong>{{ t.title }}</strong>
                <p>{{ t.desc }}</p>
              </div>
              <ElIcon class="tip-arrow"><ArrowRight /></ElIcon>
            </li>
          </ul>
          <a class="link-foot">查看全部建议 (6) ›</a>
        </article>

        <article class="card card-pad">
          <header class="chart-head"><h3>模型占比 (按成本)</h3></header>
          <div v-for="m in modelShare" :key="m.name" class="ms-row">
            <span class="ms-label">{{ m.name }}</span>
            <div class="ms-bar"><i :style="{ width: m.pct + '%', background: m.color }" /></div>
            <span class="ms-pct">{{ m.pct }}%</span>
          </div>
          <a class="link-foot">查看全部模型 ›</a>
        </article>

        <article class="card card-pad">
          <header class="chart-head"><h3>本月预算</h3><a class="link-mini">编辑</a></header>
          <div class="budget-block">
            <div class="bb-label">预算总额</div>
            <div class="bb-value">$ 50.00 <small>USD</small></div>
            <div class="rp-bar"><i style="width: 24%;" /></div>
            <div class="bb-foot">
              <span>已用 $12.48 (24%)</span>
              <span>剩余 $37.52</span>
            </div>
            <div class="bb-reset">预算重置:2026-06-01</div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cost { display: grid; gap: 16px; }
.demo-banner { border-radius: 8px; }

/* Filter row */
.cost-filters {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 18px;
  flex-wrap: wrap;
}
.filter-field { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 12.5px; color: var(--muted); }
.filter-grow { flex: 1; }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 36px; padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer;
}
.btn-secondary:hover { border-color: var(--primary-line); color: var(--primary); }

/* KPI grid */
.cost-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.kpi-tile { padding: 16px 18px; }
.kpi-label { font-size: 12.5px; color: var(--muted); margin-bottom: 6px; }
.kpi-value-row { display: flex; align-items: baseline; gap: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; }
.kpi-value.is-red { color: var(--red); }
.kpi-unit { font-size: 11.5px; color: var(--muted); }
.kpi-delta { font-size: 11.5px; color: var(--muted); margin-top: 8px; }
.kpi-delta.up { color: var(--red); }
.kpi-tile:nth-child(5) .kpi-value-row .kpi-unit { color: var(--red); font-weight: 700; }
.kpi-sub { color: var(--muted-soft); display: block; }

/* Budget alert */
.budget-alert {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 18px;
  background: #fff7ed;
  border-color: #fed7aa;
}
.ba-ico {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: #ffedd5;
  display: grid; place-items: center;
}
.ba-body { flex: 1; }
.ba-body strong { font-size: 13.5px; font-weight: 600; color: var(--orange-text); display: block; }
.ba-body p { margin: 4px 0 0; font-size: 12.5px; color: var(--text-soft); }
.ba-cells { display: flex; align-items: center; gap: 16px; }
.ba-cell {
  padding: 10px 18px;
  border-radius: 10px;
  background: white;
  border: 1px solid;
  text-align: center;
}
.ba-cell[data-color='red']    { border-color: #fecaca; }
.ba-cell[data-color='orange'] { border-color: #fed7aa; }
.ba-cell-val { font-size: 22px; font-weight: 700; }
.ba-cell-val small { font-size: 11px; color: var(--muted); margin-left: 4px; font-weight: 500; }
.ba-cell[data-color='red']    .ba-cell-val { color: var(--red); }
.ba-cell[data-color='orange'] .ba-cell-val { color: var(--orange); }
.ba-cell-lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }
.ba-link { display: inline-flex; align-items: center; gap: 4px; color: var(--primary); font-size: 13px; cursor: pointer; font-weight: 500; }

/* Layout */
.cost-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
  align-items: start;
}
.cost-main { display: grid; gap: 16px; min-width: 0; }
.cost-side { display: grid; gap: 16px; }

.chart-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.chart-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text); }
.chart-unit { font-size: 11px; color: var(--muted); font-family: var(--t-mono); }
.seg {
  display: inline-flex;
  background: var(--surface-3);
  border-radius: 6px;
  padding: 2px;
}
.seg button {
  padding: 4px 12px;
  border: none; background: transparent;
  font: inherit; font-size: 12px; font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  border-radius: 4px;
}
.seg button.active { background: var(--surface); color: var(--primary); box-shadow: var(--shadow-1); }

/* Donut center label */
.donut-block { position: relative; }
.donut-center {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}
.dc-val { display: block; font-size: 18px; font-weight: 700; color: var(--text); }
.dc-lbl { display: block; font-size: 11px; color: var(--muted); margin-top: 2px; }
.donut-list { list-style: none; padding: 0; margin: 12px 0 0; display: grid; gap: 6px; }
.donut-list li { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-soft); }
.donut-list li b { margin-left: auto; font-weight: 600; color: var(--text); }
.donut-list li small { color: var(--muted-soft); font-size: 11px; }
.donut-list .ld { width: 8px; height: 8px; border-radius: 50%; }

/* Task table */
.task-table { padding: 0; }
.th-row, .td-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1.1fr .6fr 1.3fr .7fr .5fr 1fr;
  gap: 10px;
  padding: 12px 22px;
  font-size: 12.5px;
  align-items: center;
}
.th-row { background: var(--surface-3); color: var(--text-soft); font-weight: 600; border-bottom: 1px solid var(--border); }
.td-row { border-bottom: 1px solid var(--border); color: var(--text-soft); }
.td-row:last-of-type { border-bottom: none; }
.td-row:hover { background: var(--surface-2); }
.td-name { display: flex; align-items: center; gap: 8px; min-width: 0; }
.td-name span:last-child {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500; color: var(--text);
}
.td-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.td-dot[data-color='blue']   { background: #2563eb; }
.td-dot[data-color='green']  { background: #16a34a; }
.td-dot[data-color='orange'] { background: #f97316; }
.td-dot[data-color='purple'] { background: #7c3aed; }
.td-dot[data-color='pink']   { background: #db2777; }
.mono { font-family: var(--t-mono); }
.td-time { color: var(--muted); font-size: 12px; font-family: var(--t-mono); }
.task-foot {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 22px;
  border-top: 1px solid var(--border);
  font-size: 13px; color: var(--muted);
  cursor: pointer;
}

/* Side: tips */
.tip-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.tip-list li {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-3);
  cursor: pointer;
  transition: background .12s ease;
}
.tip-list li:hover { background: var(--primary-soft); }
.tip-ico {
  width: 26px; height: 26px;
  border-radius: 6px;
  display: grid; place-items: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.tip-ico[data-color='blue']   { background: #dbeafe; color: #2563eb; }
.tip-ico[data-color='green']  { background: #dcfce7; color: #16a34a; }
.tip-ico[data-color='purple'] { background: #ede9fe; color: #7c3aed; }
.tip-body { flex: 1; min-width: 0; }
.tip-body strong { font-size: 12.5px; font-weight: 600; color: var(--text); display: block; }
.tip-body p { margin: 4px 0 0; font-size: 11.5px; color: var(--muted); line-height: 1.5; }
.tip-arrow { color: var(--muted-soft); font-size: 12px; align-self: center; }
.link-foot {
  display: block; text-align: center;
  margin-top: 10px; padding: 8px;
  font-size: 12.5px; color: var(--primary);
  cursor: pointer;
}
.link-mini { font-size: 12px; color: var(--primary); cursor: pointer; }

/* Model share */
.ms-row {
  display: grid;
  grid-template-columns: 90px 1fr 44px;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 12.5px;
  color: var(--text-soft);
}
.ms-bar { height: 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.ms-bar i { display: block; height: 100%; border-radius: inherit; }
.ms-pct { text-align: right; font-family: var(--t-mono); color: var(--text); font-weight: 600; font-size: 12px; }

/* Budget block */
.budget-block { padding: 4px 0 0; }
.bb-label { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.bb-value { font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; margin-bottom: 10px; }
.bb-value small { font-size: 11px; color: var(--muted); margin-left: 4px; font-weight: 500; }
.rp-bar { height: 6px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.rp-bar i { display: block; height: 100%; background: var(--primary); border-radius: inherit; }
.bb-foot { display: flex; justify-content: space-between; margin-top: 6px; font-size: 11.5px; color: var(--muted); }
.bb-reset { margin-top: 10px; font-size: 11px; color: var(--muted-soft); }

@media (max-width: 1400px) {
  .cost-kpi-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1200px) {
  .cost-grid { grid-template-columns: 1fr; }
  .chart-2col { grid-template-columns: 1fr; }
  .chart-2col article:nth-child(3) { grid-column: span 1 !important; }
}
@media (max-width: 700px) {
  .cost-kpi-grid { grid-template-columns: 1fr 1fr; }
  .budget-alert { flex-direction: column; align-items: flex-start; }
}
</style>
