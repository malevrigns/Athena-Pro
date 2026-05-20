import { onMounted, onUnmounted } from 'vue'
import { usePermissionStore } from '@/stores/permission'
import { permissionApi, type Scope } from '@/api/permissionApi'
import { wsClient } from '@/api/wsClient'  // 从 ch34 来

/**
 * 全局挂载一次(在 App.vue 里),负责:
 *  - 监听 WebSocket 的 permission_required 事件 → 入队
 *  - 暴露 decide(...) 函数给 PermissionDialog 调用
 */
export function usePermission() {
  const store = usePermissionStore()

  function onMessage(event: any) {
    if (event.type === 'permission_required') {
      store.enqueue({
        request_id: event.request_id,
        task_id: event.task_id,
        tool_name: event.tool_name,
        args: event.args,
        risk_level: event.risk_level,
        reason: event.reason,
      })
    }
  }

  onMounted(() => {
    wsClient.on('message', onMessage)
  })

  onUnmounted(() => {
    wsClient.off('message', onMessage)
  })

  /** 提交决策,成功后从队列移除 */
  async function decide(
    requestId: string,
    action: 'allow' | 'deny',
    scope: Scope
  ) {
    try {
      await permissionApi.decide(requestId, { action, scope })
      store.dequeue()
    } catch (e) {
      // 失败保持在队列里,用户可以重试
      console.error('[permission] decide failed', e)
      throw e
    }
  }

  return { decide }
}