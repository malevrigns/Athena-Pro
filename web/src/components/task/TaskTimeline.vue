<script setup lang="ts">
import { computed } from 'vue'
import { Clock, CircleCheck, WarningFilled, CircleClose, InfoFilled } from '@element-plus/icons-vue'
import type { StreamEvent } from '@/types/api'

const props = defineProps<{ events: StreamEvent[] }>()

const recent = computed(() => [...props.events].slice(-40).reverse())

function typeMeta(type: string) {
  if (type === 'error') return { color: '#ef4444', icon: CircleClose, label: 'ERROR' }
  if (type === 'done') return { color: '#10b981', icon: CircleCheck, label: 'DONE' }
  if (type === 'cancelled') return { color: '#f59e0b', icon: WarningFilled, label: 'CANCEL' }
  if (type === 'quality' || type === 'plan' || type === 'finding' || type === 'review') return { color: '#4f46e5', icon: InfoFilled, label: 'INFO' }
  return { color: '#94a3b8', icon: Clock, label: 'DEBUG' }
}

function summary(ev: StreamEvent): string {
  const p = ev.payload as Record<string, unknown>
  if (ev.type === 'route') return `iter ${p.iteration ?? '?'} → ${p.route} (findings=${p.finding_count ?? 0})`
  if (ev.type === 'plan') {
    const plan = p.plan as { topics?: unknown[] } | undefined
    return `规划 ${plan?.topics?.length ?? 0} 个 topic`
  }
  if (ev.type === 'finding') {
    const f = p.finding as { title?: string; sources?: unknown[] } | undefined
    return `${f?.title || ''} · ${f?.sources?.length ?? 0} 来源`
  }
  if (ev.type === 'quality') {
    const q = p.quality as { overall?: number } | undefined
    return `overall ${(q?.overall ?? 0).toFixed(2)}`
  }
  if (ev.type === 'usage') {
    const u = p.usage as { cost_usd?: number; node?: string; input_tokens?: number; output_tokens?: number } | undefined
    return `${u?.node ?? ''} · ${u?.input_tokens ?? 0}/${u?.output_tokens ?? 0} tok · $${(u?.cost_usd ?? 0).toFixed(5)}`
  }
  if (ev.type === 'review') return String(p.review || '').slice(0, 80)
  if (ev.type === 'done') {
    const r = p.final_report as { citations?: unknown[] } | undefined
    return `报告完成 · ${r?.citations?.length ?? 0} 引用`
  }
  if (ev.type === 'error') return String(p.error || '')
  return JSON.stringify(p).slice(0, 80)
}

function timeStr(ts?: string): string {
  if (!ts) return ''
  try { return new Date(ts).toLocaleTimeString() } catch { return '' }
}
</script>

<template>
  <ElCard shadow="never" class="athena-card timeline-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>实时事件流</strong></div>
          <p class="subtitle">SSE 持久化 · {{ events.length }} 条事件</p>
        </div>
        <ElTag :type="events.length ? 'primary' : 'info'" round size="small" effect="light">
          {{ events.length ? 'STREAMING' : 'STANDBY' }}
        </ElTag>
      </div>
    </template>

    <ElEmpty v-if="!events.length" description="任务启动后, Planner/Researcher/Quality 事件会按时间顺序出现在这里" :image-size="64" />
    <ElScrollbar v-else max-height="460px">
      <ElTimeline class="event-timeline">
        <ElTimelineItem
          v-for="(event, i) in recent"
          :key="`${event.type}-${i}`"
          :timestamp="timeStr(event.ts)"
          :color="typeMeta(event.type).color"
          placement="top"
          size="normal"
        >
          <div class="event-row">
            <div class="event-head">
              <ElTag size="small" effect="plain" :style="{ borderColor: typeMeta(event.type).color, color: typeMeta(event.type).color }">
                {{ event.type }}
              </ElTag>
              <span class="event-node">{{ event.node || '—' }}</span>
            </div>
            <p>{{ summary(event) }}</p>
          </div>
        </ElTimelineItem>
      </ElTimeline>
    </ElScrollbar>
  </ElCard>
</template>

<style scoped>
.event-timeline { padding: 4px 6px 4px 2px; }
.event-row { padding: 2px 0; }
.event-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.event-node {
  font-family: var(--athena-mono);
  font-size: 11.5px;
  color: var(--athena-muted);
  text-transform: uppercase;
  letter-spacing: .06em;
}
.event-row p {
  margin: 0;
  font-size: 13px;
  color: var(--athena-text-soft);
  line-height: 1.5;
}
.event-timeline :deep(.el-timeline-item__timestamp) {
  font-family: var(--athena-mono);
  font-size: 11px;
  color: var(--athena-muted-soft);
}
</style>
