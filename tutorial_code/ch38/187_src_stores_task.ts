import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type NodeStatus = 'pending' | 'running' | 'done' | 'failed'

export type StreamPhase =
  | 'idle'           // 还没连
  | 'connecting'     // EventSource 建立中
  | 'streaming'      // 正常收事件
  | 'done'           // 任务完成
  | 'aborted'        // 用户中断
  | 'error'          // 连接 / 处理出错

export const useTaskStore = defineStore('task', () => {
  // ===== State =====
  const taskId = ref(null)
  const phase = ref('idle')
  const errorMsg = ref(null)
  
  // 每个节点的状态
  const nodeStatuses = ref>({})
  // 当前正在产出 token 的节点
  const currentNode = ref(null)
  // 累积的 token 流(当前 segment)
  const thinking = ref('')
  // 最终报告(done 后填充)
  const finalReport = ref(null)
  const reportMetadata = ref | null>(null)
  
  // ===== Getters =====
  const isRunning = computed(() => phase.value === 'streaming')
  const isDone = computed(() => phase.value === 'done')
  
  // ===== Actions =====
  function startTask(id: string) {
    taskId.value = id
    phase.value = 'connecting'
    errorMsg.value = null
    nodeStatuses.value = { planner: 'running' }  // 立刻给视觉反馈
    currentNode.value = 'planner'
    thinking.value = ''
    finalReport.value = null
    reportMetadata.value = null
  }
  
  function markStreaming() { phase.value = 'streaming' }
  
  function onNodeUpdate(node: string) {
    nodeStatuses.value = { ...nodeStatuses.value, [node]: 'done' }
    thinking.value = ''                            // 新节点开始,清空打字机
  }
  
  function onToken(node: string | null, content: string) {
    thinking.value += content
    if (node && nodeStatuses.value[node] !== 'done') {
      currentNode.value = node
      nodeStatuses.value = { ...nodeStatuses.value, [node]: 'running' }
    }
  }
  
  function onDone(report: string | null, metadata: Record) {
    finalReport.value = report
    reportMetadata.value = metadata
    phase.value = 'done'
    // 所有节点标为 done(收尾视觉)
    const allDone: Record = {}
    for (const k of Object.keys(nodeStatuses.value)) allDone[k] = 'done'
    nodeStatuses.value = allDone
  }
  
  function onError(msg: string) {
    errorMsg.value = msg
    phase.value = 'error'
  }
  
  function markAborted() { phase.value = 'aborted' }
  
  function reset() {
    taskId.value = null
    phase.value = 'idle'
    nodeStatuses.value = {}
    currentNode.value = null
    thinking.value = ''
    finalReport.value = null
    reportMetadata.value = null
    errorMsg.value = null
  }
  
  return {
    // state
    taskId, phase, errorMsg, nodeStatuses, currentNode,
    thinking, finalReport, reportMetadata,
    // getters
    isRunning, isDone,
    // actions
    startTask, markStreaming, onNodeUpdate, onToken,
    onDone, onError, markAborted, reset,
  }
})