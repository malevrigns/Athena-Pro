<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { NProgress, NIcon, NSkeleton } from 'naive-ui'
import { AlertTriangle } from 'lucide-vue-next'
import { useCostStore } from '@/stores/cost'
import { useCost } from '@/composables/useCost'

const props = defineProps<{
  taskId: string
}>()

const store = useCostStore()

// 启动定时拉取(2 秒一次),unmounted 时自动停止
useCost(() => props.taskId)

// 派生数据:从 store 读
const info = computed(() => store.byTask[props.taskId])
const pct = computed(() => {
  if (!info.value) return 0
  return (info.value.spent_usd / info.value.budget_usd) * 100
})
const isWarning = computed(() => pct.value > 80)

// 取前 5 个最贵的节点
const topNodes = computed(() => {
  if (!info.value) return []
  return Object.entries(info.value.by_node)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
})
</script>

<template>
  <div class="space-y-4">
    <NSkeleton v-if="!info" :repeat="3" />
    <template v-else>
      <!-- 当前任务成本 -->
      <div>
        <h3 class="font-serif text-sm tracking-wider text-stone-500 uppercase mb-2">
          本次任务成本
        </h3>
        <div class="text-2xl font-semibold text-stone-900">
          ${{ info.spent_usd.toFixed(3) }}
        </div>
        <p class="text-xs text-stone-500 mt-1">
          / 预算 ${{ info.budget_usd.toFixed(2) }}
        </p>
      </div>

      <!-- 进度条 -->
      <NProgress
        type="line"
        :percentage="Math.min(pct, 100)"
        :show-indicator="false"
        :height="6"
        :color="isWarning ? '#f59e0b' : '#fb923c'"
        rail-color="rgba(0,0,0,0.05)"
      />

      <!-- 预算警告 -->
      <div
        v-if="isWarning"
        class="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800"
      >
        <NIcon :component="AlertTriangle" :size="16" class="shrink-0 mt-0.5" />
        <span>已使用 {{ pct.toFixed(0) }}% 预算,接近上限</span>
      </div>

      <!-- 按节点分布 (Top 5) -->
      <div>
        <div class="text-xs uppercase tracking-wider text-stone-400 mb-2">按节点</div>
        <div class="space-y-1.5">
          <div
            v-for="[node, cost] in topNodes"
            :key="node"
            class="flex items-center justify-between text-xs"
          >
            <span class="text-stone-600">{{ node }}</span>
            <span class="font-mono text-stone-900">${{ cost.toFixed(3) }}</span>
          </div>
        </div>
      </div>

      <div class="text-xs text-stone-400 pt-2 border-t border-stone-100">
        {{ info.n_llm_calls }} 次 LLM 调用
      </div>
    </template>
  </div>
</template>