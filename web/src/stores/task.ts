import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  createTask,
  downloadFile,
  exportReport,
  getTask,
  interruptTask,
  listTasks,
} from '@/api/client'
import { openTaskStream } from '@/api/stream'
import type {
  Finding,
  FinalReport,
  QualityScore,
  ResearchPlan,
  ResearchTopic,
  StreamEvent,
  TaskSnapshot,
  TaskStatus,
} from '@/types/api'

interface RouteEvent {
  iteration?: number
  route?: string
  quality?: number | null
  finding_count?: number
  topic_count?: number
}

export const useTaskStore = defineStore('task', () => {
  const current = ref<TaskSnapshot | null>(null)
  const events = ref<StreamEvent[]>([])
  const writerStream = ref<string>('')
  const reviewerNotes = ref<string[]>([])
  const supervisorIterations = ref<RouteEvent[]>([])
  const tasks = ref<TaskSnapshot[]>([])
  const stream = ref<{ close: () => void } | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastExport = ref<{ format: string; url: string; filename: string } | null>(null)
  const lastSeq = ref(0)
  let requestGeneration = 0

  const status = computed<TaskStatus>(() => current.value?.status ?? 'created')
  const plan = computed<ResearchPlan | null>(() => current.value?.plan ?? null)
  const findings = computed<Finding[]>(() => current.value?.findings ?? [])
  const finalReport = computed<FinalReport | null>(() => current.value?.final_report ?? null)
  const quality = computed<QualityScore | null>(() => current.value?.quality ?? null)
  const sources = computed(() => {
    const out: { source_id: string; title: string; url: string; snippet?: string }[] = []
    const seen = new Set<string>()
    for (const f of findings.value) {
      for (const s of f.sources) {
        if (seen.has(s.url)) continue
        seen.add(s.url)
        out.push({ source_id: s.id, title: s.title, url: s.url, snippet: s.snippet })
      }
    }
    return out
  })
  const isRunning = computed(() =>
    current.value !== null
    && ['created', 'planning', 'waiting_review', 'researching', 'quality_gate', 'writing'].includes(status.value)
  )
  const isTerminal = computed(() => ['done', 'failed', 'cancelled'].includes(status.value))
  const progress = computed(() => {
    const map: Record<TaskStatus, number> = {
      created: 4,
      planning: 18,
      waiting_review: 28,
      researching: 55,
      quality_gate: 72,
      writing: 88,
      done: 100,
      failed: 100,
      cancelled: 100,
    }
    return map[status.value]
  })

  function applyEvent(event: StreamEvent) {
    if (!current.value) return
    if (event.task_id !== current.value.id) return
    if (event.seq > 0 && event.seq <= lastSeq.value) return
    if (event.seq > 0) lastSeq.value = event.seq
    events.value.push(event)
    const payload = event.payload as Record<string, unknown>
    if (event.type === 'status') {
      current.value.status = payload.status as TaskStatus
    } else if (event.type === 'plan') {
      current.value.plan = payload.plan as ResearchPlan
    } else if (event.type === 'plan_expanded') {
      const newTopics = payload.new_topics as ResearchTopic[]
      if (current.value.plan) {
        current.value.plan.topics = [...current.value.plan.topics, ...newTopics]
      }
    } else if (event.type === 'finding') {
      current.value.findings = [...current.value.findings, payload.finding as Finding]
    } else if (event.type === 'quality') {
      current.value.quality = payload.quality as QualityScore
    } else if (event.type === 'review') {
      const review = String(payload.review || '')
      if (review) reviewerNotes.value = [...reviewerNotes.value, review]
    } else if (event.type === 'route') {
      supervisorIterations.value = [...supervisorIterations.value, payload as RouteEvent]
    } else if (event.type === 'done') {
      const report = payload.final_report as FinalReport
      current.value.final_report = report
      writerStream.value = report?.markdown || ''
      current.value.status = 'done'
    } else if (event.type === 'usage') {
      const usage = payload.usage as { cost_usd?: number } | undefined
      if (usage?.cost_usd) current.value.cost_usd = (current.value.cost_usd || 0) + usage.cost_usd
    } else if (event.type === 'cancelled') {
      current.value.status = 'cancelled'
    } else if (event.type === 'error') {
      current.value.status = 'failed'
      error.value = String(payload.error || 'unknown error')
    }
  }

  function _reset() {
    events.value = []
    writerStream.value = ''
    reviewerNotes.value = []
    supervisorIterations.value = []
    lastExport.value = null
    error.value = null
    lastSeq.value = 0
  }

  async function start(question: string, userId = 'demo-user') {
    const generation = ++requestGeneration
    loading.value = true
    closeStream()
    _reset()
    try {
      const response = await createTask(question, userId)
      if (generation !== requestGeneration) return
      current.value = response.snapshot
      lastSeq.value = response.snapshot.events_count
      stream.value = openTaskStream(
        response.task_id,
        applyEvent,
        (err) => {
          error.value = err instanceof Error ? err.message : String(err)
        },
        undefined,
        lastSeq.value,
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function load(id: string, subscribe = true) {
    const generation = ++requestGeneration
    closeStream()
    _reset()
    try {
      const snapshot = await getTask(id)
      if (generation !== requestGeneration) return
      current.value = snapshot
      lastSeq.value = snapshot.events_count
      if (subscribe && current.value && !['done', 'failed', 'cancelled'].includes(current.value.status)) {
        stream.value = openTaskStream(id, applyEvent, (err) => {
          error.value = err instanceof Error ? err.message : String(err)
        }, undefined, lastSeq.value)
      }
      if (current.value?.final_report?.markdown) writerStream.value = current.value.final_report.markdown
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  async function refreshTasks() {
    try {
      tasks.value = await listTasks()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }

  async function stop() {
    if (!current.value) return
    const stopped = await interruptTask(current.value.id)
    if (!stopped) throw new Error('task not found or cannot be interrupted')
    current.value.status = 'cancelled'
  }

  async function downloadReport(fmt: 'md' | 'html' | 'pdf' | 'docx') {
    if (!current.value) return
    const resp = await exportReport(current.value.id, fmt)
    const url = await downloadFile(resp.download_url, resp.filename)
    lastExport.value = { format: fmt, url, filename: resp.filename }
    return resp
  }

  function closeStream() {
    stream.value?.close()
    stream.value = null
  }

  return {
    current,
    events,
    writerStream,
    reviewerNotes,
    supervisorIterations,
    tasks,
    loading,
    error,
    lastExport,
    status,
    plan,
    findings,
    finalReport,
    quality,
    sources,
    isRunning,
    isTerminal,
    progress,
    start,
    load,
    refreshTasks,
    stop,
    downloadReport,
    closeStream,
  }
})
