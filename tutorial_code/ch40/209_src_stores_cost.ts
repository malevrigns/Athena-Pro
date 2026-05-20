import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface TaskCostInfo {
  spent_usd: number
  budget_usd: number
  by_model: Record<string, number>
  by_node: Record<string, number>
  n_llm_calls: number
}

export interface MonthlyCostInfo {
  total: number
  budget: number
  daily: { date: string; cost: number }[]
  by_model: { model: string; cost: number }[]
  by_node: { node: string; cost: number }[]
}

export const useCostStore = defineStore('cost', () => {
  // 当前任务的成本(按 taskId 索引,因为多任务可能并存)
  const byTask = ref<Record<string, TaskCostInfo>>({})

  // 当前用户本月的成本汇总
  const monthly = ref<MonthlyCostInfo | null>(null)

  function setTaskCost(taskId: string, info: TaskCostInfo) {
    byTask.value[taskId] = info
  }

  function setMonthly(info: MonthlyCostInfo) {
    monthly.value = info
  }

  // 任务结束时调,腾出内存
  function clearTask(taskId: string) {
    delete byTask.value[taskId]
  }

  return { byTask, monthly, setTaskCost, setMonthly, clearTask }
})