import { onMounted, onUnmounted, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { useCostStore } from '@/stores/cost'
import { apiClient } from '@/api/client'

const POLL_INTERVAL_MS = 2000

/**
 * 给某个 task 启动成本数据的定时轮询。
 *
 * 用法:在组件 setup 顶层调用 useCost(() => props.taskId)。
 * 组件卸载后自动停止轮询。task id 变化时自动重启轮询。
 */
export function useCost(taskIdSource: MaybeRefOrGetter<string>) {
  const store = useCostStore()
  let timerId: number | undefined

  async function poll() {
    const id = toValue(taskIdSource)
    if (!id) return
    try {
      const data = await apiClient.getTaskCost(id)
      store.setTaskCost(id, data)
    } catch (e) {
      // 静默失败:成本数据轮询不应该影响主流程
      console.warn('[useCost] poll failed', e)
    }
  }

  function start() {
    stop()
    poll()  // 立即跑一次
    timerId = window.setInterval(poll, POLL_INTERVAL_MS)
  }

  function stop() {
    if (timerId) {
      window.clearInterval(timerId)
      timerId = undefined
    }
  }

  onMounted(start)
  onUnmounted(stop)

  // 如果 taskId 变了,重启轮询
  watch(() => toValue(taskIdSource), () => {
    if (timerId) start()
  })
}