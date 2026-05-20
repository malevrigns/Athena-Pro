<script setup lang="ts">
import { computed, watch } from 'vue'
import { VueFlow, useVueFlow, type Edge, type Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import type { TaskStatus } from '@/types/api'

const props = defineProps<{ status: TaskStatus; progress: number; findings?: number; iteration?: number }>()

const activeMap = computed(() => ({
  planner: ['planning', 'waiting_review', 'researching', 'quality_gate', 'writing', 'done'].includes(props.status),
  review: ['waiting_review', 'researching', 'quality_gate', 'writing', 'done'].includes(props.status),
  researcher: ['researching', 'quality_gate', 'writing', 'done'].includes(props.status),
  quality: ['quality_gate', 'writing', 'done'].includes(props.status),
  reviewer: (props.iteration ?? 1) > 1,
  writer: ['writing', 'done'].includes(props.status),
}))

type StyleMap = Record<string, string | number>
const baseStyle: StyleMap = {
  padding: '8px 14px',
  borderRadius: '8px',
  border: '1px solid var(--athena-border)',
  background: 'var(--athena-surface)',
  fontWeight: 600,
  minWidth: '140px',
  color: 'var(--athena-text)',
  fontSize: '13px',
  boxShadow: 'var(--athena-shadow-sm)',
}
const accent = (on: boolean): StyleMap => on
  ? { ...baseStyle, borderColor: 'var(--el-color-primary)', color: 'var(--el-color-primary)', boxShadow: '0 0 0 3px var(--el-color-primary-light-9)' }
  : { ...baseStyle }
const done = (on: boolean): StyleMap => on
  ? { ...baseStyle, background: 'var(--el-color-success)', color: 'white', borderColor: 'var(--el-color-success)', boxShadow: '0 6px 18px rgba(16,185,129,.35)' }
  : { ...baseStyle }

const nodes = computed<Node[]>(() => {
  const active = activeMap.value
  return [
    { id: 'planner', position: { x: 40, y: 40 }, data: { label: '📐 Planner' }, style: accent(active.planner), draggable: false, selectable: false },
    { id: 'review', position: { x: 240, y: 40 }, data: { label: '🤝 Plan Review' }, style: accent(active.review), draggable: false, selectable: false },
    { id: 'supervisor', position: { x: 440, y: 40 }, data: { label: '🧭 Supervisor' }, style: accent(active.researcher), draggable: false, selectable: false },
    { id: 'researcher_a', position: { x: 200, y: 180 }, data: { label: '🔍 Researcher A' }, style: accent(active.researcher), draggable: false, selectable: false },
    { id: 'researcher_b', position: { x: 400, y: 180 }, data: { label: '🔍 Researcher B' }, style: accent(active.researcher), draggable: false, selectable: false },
    { id: 'researcher_n', position: { x: 600, y: 180 }, data: { label: '🔍 Researcher …' }, style: accent(active.researcher), draggable: false, selectable: false },
    { id: 'quality', position: { x: 440, y: 320 }, data: { label: '✅ Quality Gate' }, style: accent(active.quality), draggable: false, selectable: false },
    { id: 'reviewer', position: { x: 220, y: 320 }, data: { label: '🧐 Reviewer' }, style: accent(active.reviewer), draggable: false, selectable: false },
    { id: 'writer', position: { x: 700, y: 320 }, data: { label: '🖋 Writer' }, style: done(active.writer), draggable: false, selectable: false },
  ]
})

const edges: Edge[] = [
  { id: 'e1', source: 'planner', target: 'review', animated: true },
  { id: 'e2', source: 'review', target: 'supervisor', animated: true },
  { id: 'e3', source: 'supervisor', target: 'researcher_a', animated: true },
  { id: 'e4', source: 'supervisor', target: 'researcher_b', animated: true },
  { id: 'e5', source: 'supervisor', target: 'researcher_n', animated: true },
  { id: 'e6', source: 'researcher_a', target: 'quality' },
  { id: 'e7', source: 'researcher_b', target: 'quality' },
  { id: 'e8', source: 'researcher_n', target: 'quality' },
  { id: 'e9', source: 'quality', target: 'reviewer', label: 'quality<阈值', style: { stroke: '#94a3b8' } },
  { id: 'e10', source: 'reviewer', target: 'supervisor', animated: true, label: '补充调研', style: { stroke: '#f59e0b' } },
  { id: 'e11', source: 'quality', target: 'writer', animated: true, label: '通过', style: { stroke: '#10b981' } },
]

const { fitView } = useVueFlow()
watch(() => props.status, () => setTimeout(() => fitView({ padding: 0.1 }), 60))
</script>

<template>
  <ElCard shadow="never" class="athena-card workflow-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>多 Agent 流水线</strong></div>
          <p class="subtitle">
            状态 <b>{{ status }}</b> · 进度 {{ progress }}% · 迭代轮 {{ iteration ?? 1 }} · {{ findings ?? 0 }} findings
          </p>
        </div>
        <ElTag round size="small" :type="status === 'done' ? 'success' : status === 'failed' || status === 'cancelled' ? 'danger' : 'primary'">
          {{ status }}
        </ElTag>
      </div>
    </template>

    <div class="vue-flow-wrapper">
      <VueFlow
        :nodes="nodes"
        :edges="edges"
        :fit-view-on-init="true"
        :nodes-draggable="false"
        :pan-on-drag="false"
        :zoom-on-double-click="false"
      >
        <Background pattern-color="var(--athena-border)" :gap="18" />
        <Controls />
        <MiniMap mask-color="rgba(15,23,42,.05)" />
      </VueFlow>
    </div>
  </ElCard>
</template>

<style scoped>
.vue-flow-wrapper {
  height: 460px;
  border: 1px solid var(--athena-border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--athena-surface-soft);
}
</style>
