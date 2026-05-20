<script setup lang="ts">
import { toRef } from 'vue'
import { storeToRefs } from 'pinia'
import { NTag } from 'naive-ui'
import { useTaskStore } from '@/stores/task'
import { useEventStream } from '@/composables/useEventStream'
import FlowGraph from './FlowGraph.vue'
import ThinkingPane from './ThinkingPane.vue'
import StopButton from './StopButton.vue'
import CostPanel from './CostPanel.vue'
import ReportRenderer from '@/components/report/ReportRenderer.vue'

const props = defineProps<{ taskId: string }>()

// 启动 SSE 流(组合式函数自己管生命周期)
useEventStream(toRef(props, 'taskId'))

// 从 store 拿响应式数据
const taskStore = useTaskStore()
const {
  nodeStatuses, thinking, finalReport, reportMetadata,
  phase, isRunning,
} = storeToRefs(taskStore)

const phaseLabel: Record<string, string> = {
  connecting: '连接中',
  streaming: '运行中',
  done: '完成',
  aborted: '已中止',
  error: '错误',
  idle: '空闲',
}
</script>

<template>
  <div class="grid grid-cols-12 gap-6 h-full">
    <!-- 左:节点流程图 -->
    <aside class="col-span-3 border-r border-stone-200 px-4 py-6">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="font-serif text-sm tracking-wider text-stone-500 uppercase">
          执行流程
        </h3>
        <NTag :type="isRunning ? 'warning' : 'default'" size="small">
          {{ phaseLabel[phase] }}
        </NTag>
      </div>
      <FlowGraph :statuses="nodeStatuses" />
      <StopButton v-if="isRunning" class="mt-6" />
    </aside>
    
    <!-- 中:思考流 / 最终报告 -->
    <main class="col-span-6 overflow-auto px-6 py-6">
      <ReportRenderer
        v-if="finalReport"
        :markdown="finalReport"
        :metadata="reportMetadata"
      />
      <ThinkingPane
        v-else
        :content="thinking"
        :show-cursor="isRunning"
      />
    </main>
    
    <!-- 右:成本面板 -->
    <aside class="col-span-3 border-l border-stone-200 px-4 py-6">
      <CostPanel :task-id="taskId" />
    </aside>
  </div>
</template>