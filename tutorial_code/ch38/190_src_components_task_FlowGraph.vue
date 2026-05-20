<script setup lang="ts">
import { computed } from 'vue'
import type { NodeStatus } from '@/stores/task'

interface NodeDef {
  id: string
  label: string
  row: number
  col: number
}

const props = defineProps<{
  statuses: Record<string, NodeStatus>
}>()

// 节点拓扑写死(Athena 主图固定)
const NODES: NodeDef[] = [
  { id: 'planner',            label: 'Planner',     row: 0, col: 1 },
  { id: 'plan_review',        label: 'PlanReview',  row: 1, col: 1 },
  { id: 'supervisor',         label: 'Supervisor',  row: 2, col: 1 },
  { id: 'researcher',         label: 'Researcher',  row: 3, col: 0 },
  { id: 'fact_check',         label: 'FactCheck',   row: 3, col: 1 },
  { id: 'citation_validator', label: 'Citation',    row: 3, col: 2 },
  { id: 'writer',             label: 'Writer',      row: 4, col: 1 },
  { id: 'reviewer',           label: 'Reviewer',    row: 5, col: 1 },
]

const EDGES: [string, string][] = [
  ['planner', 'plan_review'],
  ['plan_review', 'supervisor'],
  ['supervisor', 'researcher'],
  ['supervisor', 'fact_check'],
  ['supervisor', 'citation_validator'],
  ['researcher', 'writer'],
  ['fact_check', 'writer'],
  ['citation_validator', 'writer'],
  ['writer', 'reviewer'],
]

const W = 280, H = 460
const COL_W = W / 3, ROW_H = H / 7
const NODE_W = 80, NODE_H = 32

function nodeXY(n: NodeDef) {
  return {
    x: n.col * COL_W + COL_W / 2,
    y: n.row * ROW_H + ROW_H / 2 + 20,
  }
}

const COLORS: Record<NodeStatus, { bg: string; ring: string; text: string }> = {
  pending: { bg: '#f5f5f4', ring: '#e7e5e4', text: '#a8a29e' },
  running: { bg: '#fed7aa', ring: '#fb923c', text: '#9a3412' },
  done:    { bg: '#d1fae5', ring: '#10b981', text: '#065f46' },
  failed:  { bg: '#fecaca', ring: '#ef4444', text: '#7f1d1d' },
}

const nodeMap = computed(() => new Map(NODES.map(n => [n.id, n])))

function getStatus(id: string): NodeStatus {
  return props.statuses[id] ?? 'pending'
}
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="w-full h-auto">
    <!-- 边 -->
    <line
      v-for="([from, to], i) in EDGES"
      :key="i"
      :x1="nodeXY(nodeMap.get(from)!).x"
      :y1="nodeXY(nodeMap.get(from)!).y + NODE_H / 2"
      :x2="nodeXY(nodeMap.get(to)!).x"
      :y2="nodeXY(nodeMap.get(to)!).y - NODE_H / 2"
      :stroke="getStatus(from) === 'done' && getStatus(to) !== 'pending'
               ? '#fb923c' : '#e7e5e4'"
      :stroke-width="getStatus(from) === 'done' ? 2 : 1"
      :stroke-dasharray="getStatus(from) === 'running' ? '4 3' : '0'"
    />
    
    <!-- 节点 -->
    <g v-for="n in NODES" :key="n.id">
      <rect
        :x="nodeXY(n).x - NODE_W / 2"
        :y="nodeXY(n).y - NODE_H / 2"
        :width="NODE_W" :height="NODE_H" :rx="6"
        :fill="COLORS[getStatus(n.id)].bg"
        :stroke="COLORS[getStatus(n.id)].ring"
        :stroke-width="getStatus(n.id) === 'running' ? 2 : 1"
      >
        <animate
          v-if="getStatus(n.id) === 'running'"
          attributeName="stroke-opacity"
          values="0.4;1;0.4"
          dur="1.5s"
          repeatCount="indefinite"
        />
      </rect>
      <text
        :x="nodeXY(n).x" :y="nodeXY(n).y + 4"
        text-anchor="middle"
        font-size="11"
        font-family="system-ui"
        :fill="COLORS[getStatus(n.id)].text"
        :font-weight="getStatus(n.id) === 'done' ? 600 : 400"
      >
        {{ n.label }}
      </text>
    </g>
  </svg>
</template>