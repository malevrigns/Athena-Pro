<script setup lang="ts">
import { computed } from 'vue'
import { Money } from '@element-plus/icons-vue'
import type { TaskSnapshot } from '@/types/api'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ task: TaskSnapshot | null }>()
const session = useSessionStore()

const cost = computed(() => props.task?.cost_usd ?? 0)
const quality = computed(() => props.task?.quality?.overall ?? 0)
const budgetPct = computed(() => Math.min(100, (cost.value / Math.max(0.01, session.budgetUsd)) * 100))
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>成本与质量</strong></div>
          <p class="subtitle">实时 token usage 累加</p>
        </div>
        <ElTag round size="small" effect="plain">{{ task?.events_count || 0 }} 事件</ElTag>
      </div>
    </template>
    <ElRow :gutter="14">
      <ElCol :span="12">
        <ElStatistic title="当前任务消耗" :value="cost" :precision="5" prefix="$">
          <template #prefix><ElIcon color="var(--el-color-primary)"><Money /></ElIcon></template>
        </ElStatistic>
        <ElProgress :percentage="budgetPct" :stroke-width="6" :show-text="false" style="margin-top: 6px;" />
        <ElText type="info" size="small">{{ budgetPct.toFixed(1) }}% / ${{ session.budgetUsd.toFixed(2) }}</ElText>
      </ElCol>
      <ElCol :span="12">
        <ElStatistic title="质量分" :value="quality" :precision="2" />
        <ElProgress :percentage="quality * 100" :stroke-width="6" :show-text="false" status="success" style="margin-top: 6px;" />
      </ElCol>
    </ElRow>
  </ElCard>
</template>

<style scoped>
:deep(.el-statistic__head) { color: var(--athena-muted); font-size: 12px; font-weight: 500; }
:deep(.el-statistic__number) { font-size: 22px; font-weight: 700; color: var(--athena-text); }
</style>
