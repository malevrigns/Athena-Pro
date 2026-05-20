import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface PermissionRequestItem {
  request_id: string
  tool_name: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  reason: string
  args: Record<string, unknown>
}

export const usePermissionStore = defineStore('permission', () => {
  const queue = ref<PermissionRequestItem[]>([])
  const pending = computed(() => queue.value.length)
  function enqueue(item: PermissionRequestItem) {
    if (!queue.value.some((x) => x.request_id === item.request_id)) queue.value.push(item)
  }
  function resolve(id: string) {
    queue.value = queue.value.filter((item) => item.request_id !== id)
  }
  function clear() { queue.value = [] }
  return { queue, pending, enqueue, resolve, clear }
})
