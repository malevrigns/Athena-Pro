import { onUnmounted, watch, type Ref } from 'vue'
import { useTaskStore } from '@/stores/task'
import { SseEvent } from '@/types/events'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

/**
 * 把后端 SSE 事件流接到 task store。
 * 传入响应式 taskId(Ref),id 变化时自动重连,组件卸载时自动断开。
 */
export function useEventStream(taskId: Ref) {
  const taskStore = useTaskStore()
  let es: EventSource | null = null
  
  function connect(id: string) {
    disconnect()                                  // 旧连接先清
    taskStore.startTask(id)
    
    const url = `${BASE_URL}/v1/research/${id}/stream`
    es = new EventSource(url, { withCredentials: true })
    
    es.onopen = () => {
      taskStore.markStreaming()
    }
    
    // SSE 多种 event 类型,分别监听
    const eventTypes: SseEvent['type'][] = [
      'connected', 'node_update', 'token',
      'plan_review_required', 'permission_required',
      'done', 'error',
    ]
    for (const type of eventTypes) {
      es.addEventListener(type, (e) => handleEvent(type, e as MessageEvent))
    }
    
    // 网络错误处理
    es.onerror = () => {
      // EventSource 在 EOF 也触发 onerror,要看 readyState
      if (es && es.readyState === EventSource.CLOSED && taskStore.isRunning) {
        taskStore.onError('连接断开')
        disconnect()
      }
    }
  }
  
  function handleEvent(type: SseEvent['type'], e: MessageEvent) {
    let raw: unknown
    try { raw = JSON.parse(e.data) }
    catch { console.error('SSE invalid JSON', e.data); return }
    
    // zod 验证 + 类型窄化
    const parsed = SseEvent.safeParse({ type, ...(raw as object) })
    if (!parsed.success) {
      console.error('SSE schema mismatch', parsed.error.format())
      return
    }
    const evt = parsed.data
    
    switch (evt.type) {
      case 'node_update':
        taskStore.onNodeUpdate(evt.node)
        break
      case 'token':
        taskStore.onToken(evt.node, evt.content)
        break
      case 'done':
        taskStore.onDone(evt.final_report, evt.metadata ?? {})
        disconnect()
        break
      case 'error':
        taskStore.onError(evt.error)
        disconnect()
        break
      case 'plan_review_required':
      case 'permission_required':
        // 交给 HITL/Permission store 处理(下两章实现)
        break
      // 'connected' 仅作 ack,不改 store
    }
  }
  
  function disconnect() {
    if (es) {
      es.close()
      es = null
    }
  }
  
  // 响应式监听 taskId,变化时重连
  watch(taskId, (newId) => {
    if (newId) connect(newId)
    else disconnect()
  }, { immediate: true })
  
  // 组件卸载自动清理
  onUnmounted(() => disconnect())
  
  return { disconnect }
}