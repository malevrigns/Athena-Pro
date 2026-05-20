import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PermissionRequest, PermissionDecisionRecord } from '@/api/permissionApi'

export const usePermissionStore = defineStore('permission', () => {
  // 待处理请求队列(后端可能短时间内连续推多个,FIFO 处理)
  const pendingQueue = ref<PermissionRequest[]>([])

  // 历史决策(从 API 拉的,设置页用)
  const records = ref<PermissionDecisionRecord[]>([])

  /** 当前要弹的请求(队首),为 null 表示没有待弹 */
  const currentRequest = computed(() => pendingQueue.value[0] ?? null)

  function enqueue(req: PermissionRequest) {
    // 去重:同一个 request_id 不重复入队
    if (pendingQueue.value.some(r => r.request_id === req.request_id)) return
    pendingQueue.value.push(req)
  }

  /** 处理完队首请求,弹下一个 */
  function dequeue() {
    pendingQueue.value.shift()
  }

  function setRecords(list: PermissionDecisionRecord[]) {
    records.value = list
  }

  function removeRecord(id: string) {
    records.value = records.value.filter(r => r.id !== id)
  }

  return {
    pendingQueue,
    records,
    currentRequest,
    enqueue,
    dequeue,
    setRecords,
    removeRecord,
  }
})