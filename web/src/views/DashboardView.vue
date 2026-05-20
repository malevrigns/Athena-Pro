<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { useEntrance, runCountUp } from '@/composables/useAnime'
import { nextTick } from 'vue'

useEntrance('.stat', { delay: (_el, i) => 80 + i * 70 })
useEntrance('.bucket-row, .bucket-card', { delay: (_el, i) => 280 + i * 60 })

const task = useTaskStore()
const session = useSessionStore()
onMounted(() => task.refreshTasks())

const totalCost = computed(() => task.tasks.reduce((s, t) => s + (t.cost_usd || 0), 0))
const doneCount = computed(() => task.tasks.filter((t) => t.status === 'done').length)
const avgQuality = computed(() => {
  const filtered = task.tasks.filter((t) => t.quality)
  if (!filtered.length) return 0
  return filtered.reduce((s, t) => s + (t.quality?.overall || 0), 0) / filtered.length
})
const budgetPct = computed(() => Math.min(100, (totalCost.value / Math.max(0.01, session.budgetUsd)) * 100))

const buckets = computed(() => {
  const m: Record<string, number> = {}
  for (const t of task.tasks) m[t.status] = (m[t.status] || 0) + 1
  return Object.entries(m).map(([name, count]) => ({ name, count }))
})

function bucketColor(name: string) {
  if (name === 'done') return 'var(--ok)'
  if (name === 'failed' || name === 'cancelled') return 'var(--err)'
  if (['researching', 'writing', 'planning'].includes(name)) return 'var(--brand)'
  return 'var(--muted)'
}
</script>

<template>
  <div class="dashboard-page">
    <div class="page-head">
      <div>
        <h2>用量与质量</h2>
        <p>从 SQLite 中聚合的真实运行数据</p>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat">
        <span class="label">本月消耗</span>
        <span class="value">${{ totalCost.toFixed(4) }}</span>
        <div class="bar"><i :style="{ width: `${budgetPct}%`, background: 'var(--brand)' }" /></div>
        <span class="hint">{{ budgetPct.toFixed(1) }}% / ${{ session.budgetUsd.toFixed(2) }}</span>
      </div>
      <div class="stat">
        <span class="label">已完成任务</span>
        <span class="value">{{ doneCount }} <small>/ {{ task.tasks.length }}</small></span>
        <span class="hint">已写出报告的数量</span>
      </div>
      <div class="stat">
        <span class="label">平均质量分</span>
        <span class="value">{{ avgQuality.toFixed(2) }}</span>
        <div class="bar"><i :style="{ width: `${avgQuality * 100}%`, background: 'var(--ok)' }" /></div>
        <span class="hint">来自 Quality Gate</span>
      </div>
      <div class="stat">
        <span class="label">任务总数</span>
        <span class="value">{{ task.tasks.length }}</span>
        <span class="hint">含所有状态</span>
      </div>
    </div>

    <section class="bucket-card">
      <header>
        <h3>状态分布</h3>
        <p>{{ buckets.length }} 种状态</p>
      </header>
      <ElEmpty v-if="!buckets.length" description="还没有任务数据" :image-size="64" />
      <div v-else class="buckets">
        <div v-for="b in buckets" :key="b.name" class="bucket-row">
          <span class="bucket-name">
            <i :style="{ background: bucketColor(b.name) }" />
            {{ b.name }}
          </span>
          <div class="bucket-bar">
            <i :style="{ width: `${(b.count / Math.max(1, task.tasks.length)) * 100}%`, background: bucketColor(b.name) }" />
          </div>
          <span class="bucket-count">{{ b.count }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-page { display: grid; gap: 18px; max-width: 1100px; }
.page-head h2 { margin: 0; font-size: var(--t-22); font-weight: 600; letter-spacing: -.015em; }
.page-head p { margin: 4px 0 0; font-size: 12.5px; color: var(--muted); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.stat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-3);
  box-shadow: var(--shadow-1);
  padding: 16px 18px;
  display: grid; gap: 6px;
}
.stat .label { font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.stat .value { font-size: 26px; font-weight: 700; color: var(--text); letter-spacing: -.015em; line-height: 1.1; }
.stat .value small { font-size: 14px; color: var(--muted); font-weight: 500; }
.stat .hint { font-size: 11.5px; color: var(--muted); }
.stat .bar { height: 4px; border-radius: 999px; background: var(--surface-2); overflow: hidden; margin-top: 2px; }
.stat .bar i { display: block; height: 100%; border-radius: inherit; transition: width .25s ease; }

.bucket-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-3);
  box-shadow: var(--shadow-1);
}
.bucket-card header { padding: 14px 18px; border-bottom: 1px solid var(--border); }
.bucket-card h3 { margin: 0; font-size: var(--t-15); font-weight: 600; }
.bucket-card p { margin: 4px 0 0; font-size: 12px; color: var(--muted); }
.buckets { padding: 12px 18px; display: grid; gap: 12px; }
.bucket-row { display: grid; grid-template-columns: 140px 1fr 40px; align-items: center; gap: 14px; }
.bucket-name {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--text);
}
.bucket-name i { width: 8px; height: 8px; border-radius: 50%; }
.bucket-bar { height: 6px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.bucket-bar i { display: block; height: 100%; }
.bucket-count { text-align: right; font-family: var(--t-mono); font-size: 12px; color: var(--text); }
</style>
