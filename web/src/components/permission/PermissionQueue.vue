<script setup lang="ts">
import { computed } from 'vue'
import { useTaskStore } from '@/stores/task'

const task = useTaskStore()

const items = computed(() => {
  const out: { tool: string; risk: string; reason: string; ts: string }[] = []
  for (const ev of task.events) {
    if (ev.type !== 'review_decision') continue
    const p = ev.payload as Record<string, unknown>
    out.push({
      tool: String(p.tool_name || 'review'),
      risk: String(p.risk_level || 'medium'),
      reason: String(p.comments || p.reason || ''),
      ts: ev.ts || '',
    })
  }
  return out
})

function riskType(r: string) {
  if (r === 'critical' || r === 'high') return 'danger'
  if (r === 'medium') return 'warning'
  return 'success'
}
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>权限与审阅</strong></div>
          <p class="subtitle">人工审阅决定 (plan_review / 高风险工具)</p>
        </div>
        <ElTag round size="small" effect="plain">{{ items.length }} 决定</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!items.length" description="审阅决定会出现在这里" :image-size="56" />
    <div v-else class="perm-list">
      <div v-for="(it, i) in items" :key="i" class="perm-row">
        <div class="info">
          <strong>{{ it.tool }}</strong>
          <p>{{ it.reason || '(无备注)' }}</p>
        </div>
        <ElTag :type="riskType(it.risk)" size="small" round>{{ it.risk }}</ElTag>
      </div>
    </div>
  </ElCard>
</template>

<style scoped>
.perm-list { display: grid; gap: 8px; }
.perm-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--athena-border); border-radius: 8px; background: var(--athena-surface-soft); }
.perm-row .info { flex: 1; }
.perm-row strong { font-size: 13.5px; }
.perm-row p { margin: 2px 0 0; color: var(--athena-muted); font-size: 12px; }
</style>
