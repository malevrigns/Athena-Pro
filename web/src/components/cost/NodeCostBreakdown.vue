<script setup lang="ts">
import { computed } from 'vue'
import { useTaskStore } from '@/stores/task'

const task = useTaskStore()

interface Row {
  node: string
  cost: number
  inputTok: number
  outputTok: number
  calls: number
}

const usage = computed<Row[]>(() => {
  const byNode = new Map<string, Row>()
  for (const ev of task.events) {
    if (ev.type !== 'usage') continue
    const u = (ev.payload as { usage?: Record<string, unknown> }).usage
    if (!u) continue
    const node = String(u.node || ev.node || 'unknown')
    const entry = byNode.get(node) || { node, cost: 0, inputTok: 0, outputTok: 0, calls: 0 }
    entry.cost += Number(u.cost_usd || 0)
    entry.inputTok += Number(u.input_tokens || 0)
    entry.outputTok += Number(u.output_tokens || 0)
    entry.calls += 1
    byNode.set(node, entry)
  }
  return Array.from(byNode.values()).sort((a, b) => b.cost - a.cost)
})

const max = computed(() => Math.max(0.000001, ...usage.value.map((r) => r.cost)))
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>节点 Token / Cost</strong></div>
          <p class="subtitle">实时聚合各 agent 的输入/输出 token 与 USD 开销</p>
        </div>
        <ElTag round size="small" effect="plain">{{ usage.length }} 节点</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!usage.length" description="任务运行后展示每个 agent 的真实 token 与成本" :image-size="56" />
    <ElTable v-else :data="usage" stripe size="small">
      <ElTableColumn label="节点" width="120">
        <template #default="{ row }">
          <ElTag size="small" effect="plain" round>{{ row.node }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="调用次数" width="100" align="right" prop="calls" />
      <ElTableColumn label="输入 Token" width="110" align="right">
        <template #default="{ row }"><code class="mono">{{ row.inputTok }}</code></template>
      </ElTableColumn>
      <ElTableColumn label="输出 Token" width="110" align="right">
        <template #default="{ row }"><code class="mono">{{ row.outputTok }}</code></template>
      </ElTableColumn>
      <ElTableColumn label="花费 (USD)" width="120" align="right">
        <template #default="{ row }"><code class="mono cost">${{ row.cost.toFixed(5) }}</code></template>
      </ElTableColumn>
      <ElTableColumn label="占比">
        <template #default="{ row }">
          <ElProgress :percentage="(row.cost / max) * 100" :stroke-width="8" :show-text="false" />
        </template>
      </ElTableColumn>
    </ElTable>
  </ElCard>
</template>

<style scoped>
.mono { font-family: var(--athena-mono); font-size: 11.5px; color: var(--athena-muted); }
.mono.cost { color: var(--el-color-primary); font-weight: 600; }
</style>
