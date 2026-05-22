import { computed } from 'vue'
import { useTaskStore } from '@/stores/task'

export interface LiveEvent {
  time: string
  actor: string
  title: string
  detail: string
  type: string
}

function formatTime(ts?: string): string {
  if (!ts) return '--:--:--'
  try {
    return new Date(ts).toTimeString().slice(0, 8)
  } catch {
    return '--:--:--'
  }
}

/**
 * Display-ready views over the task store's live SSE event log:
 * a human-readable activity feed and the running token total.
 */
export function useTaskEvents() {
  const task = useTaskStore()

  const liveEvents = computed<LiveEvent[]>(() =>
    [...task.events].slice(-10).reverse().map((ev) => {
      const p = ev.payload as Record<string, any>
      let title = ''
      let detail = ''
      let actor = ''
      if (ev.type === 'plan') {
        title = 'Planner 已生成研究计划'
        detail = `计划包含 ${(p.plan?.topics?.length ?? 0)} 个核心研究方向`
        actor = 'planner'
      } else if (ev.type === 'finding') {
        title = `${ev.node || 'Researcher'} 已完成 ${(p.finding?.sources?.length ?? 0)} 个来源`
        detail = p.finding?.title || ''
        actor = 'researcher'
      } else if (ev.type === 'route') {
        title = '协调中'
        detail = `iter ${p.iteration} → ${p.route}`
        actor = 'supervisor'
      } else if (ev.type === 'quality') {
        title = 'Quality Gate 已评分'
        detail = `overall = ${(p.quality?.overall ?? 0).toFixed(2)}`
        actor = 'quality'
      } else if (ev.type === 'review') {
        title = 'Reviewer 已审阅'
        detail = String(p.review || '').slice(0, 80)
        actor = 'reviewer'
      } else if (ev.type === 'usage') {
        title = `${p.usage?.node || ''} 用量上报`
        detail = `${p.usage?.input_tokens || 0}/${p.usage?.output_tokens || 0} tok`
        actor = 'usage'
      } else if (ev.type === 'done') {
        title = '报告已生成'
        detail = `${p.final_report?.citations?.length ?? 0} 条引用`
        actor = 'writer'
      } else if (ev.type === 'created') {
        title = '任务已启动'
        detail = '正在初始化并行研究环境…'
        actor = 'system'
      } else if (ev.type === 'status') {
        title = `进入 ${p.status} 阶段`
        detail = ''
        actor = String(ev.node || 'system')
      } else if (ev.type === 'error') {
        title = '发生错误'
        detail = String(p.error || '')
        actor = 'system'
      } else {
        title = ev.type
        detail = ''
        actor = String(ev.node || '')
      }
      return { time: formatTime(ev.ts), actor, title, detail, type: ev.type }
    }),
  )

  const tokenUsed = computed(() => {
    const usage = task.events
      .filter((e) => e.type === 'usage')
      .map((e) => (e.payload as any).usage || {})
    const input = usage.reduce((s: number, u: any) => s + (u.input_tokens || 0), 0)
    const output = usage.reduce((s: number, u: any) => s + (u.output_tokens || 0), 0)
    return { input, output, total: input + output }
  })

  return { liveEvents, tokenUsed }
}
