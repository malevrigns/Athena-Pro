import { http } from '@/utils/http'
import { useTaskStore } from '@/stores/task'

export function useTaskControl() {
  const taskStore = useTaskStore()
  
  async function interrupt() {
    if (!taskStore.taskId || !taskStore.isRunning) return
    try {
      await http(`/v1/research/${taskStore.taskId}/interrupt`, {
        method: 'POST',
      })
      taskStore.markAborted()
    } catch (e) {
      console.error('interrupt failed', e)
    }
  }
  
  async function approvePlan(decision: {
    action: 'approve' | 'modify' | 'reject'
    modified_plan?: string[] | null
  }) {
    if (!taskStore.taskId) return
    await http(`/v1/research/${taskStore.taskId}/plan_decision`, {
      method: 'POST',
      body: decision,
    })
  }
  
  async function decidePermission(requestId: string, decision: {
    action: 'allow' | 'deny'
    scope: 'once' | 'session' | 'forever'
  }) {
    await http(`/v1/permissions/${requestId}/decide`, {
      method: 'POST',
      body: decision,
    })
  }
  
  return { interrupt, approvePlan, decidePermission }
}