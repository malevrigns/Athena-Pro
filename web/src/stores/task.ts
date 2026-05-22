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
import { AthenaEvent } from '@/types/api'
import type {
  AthenaEvent as AthenaEventType,
  Finding,
  FinalReport,
  QualityScore,
  ResearchPlan,
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

type TaskEventHandlerMap = {
  [K in AthenaEventType['type']]: (event: Extract<AthenaEventType, { type: K }>, snapshot: TaskSnapshot) => void
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
  // Set when a `citation_review` event arrives live; AppShell watches it to
  // prompt the user (manual mode) or toast the result (auto mode).
  const citationReview = ref<
    { taskId: string; mode: string; total: number; counts: { pass: number; flag: number; reject: number } } | null
  >(null)
  // Set when a `review_required` event arrives live — AppShell prompts the
  // user to approve the plan before research proceeds.
  const planReview = ref<{ taskId: string; stage: string; topicCount: number } | null>(null)
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

  const eventHandlers: TaskEventHandlerMap = {
    created: () => {},
    status: (event, snap) => {
      snap.status = event.payload.status
    },
    plan: (event, snap) => {
      snap.plan = event.payload.plan
    },
    plan_expanded: (event, snap) => {
      if (snap.plan) snap.plan.topics = [...snap.plan.topics, ...event.payload.new_topics]
    },
    finding: (event, snap) => {
      snap.findings = [...snap.findings, event.payload.finding]
    },
    quality: (event, snap) => {
      snap.quality = event.payload.quality
    },
    review: (event) => {
      if (event.payload.review) reviewerNotes.value = [...reviewerNotes.value, event.payload.review]
    },
    route: (event) => {
      supervisorIterations.value = [...supervisorIterations.value, {
        iteration: event.payload.iteration,
        route: event.payload.route,
        quality: event.payload.quality,
        finding_count: event.payload.finding_count,
        topic_count: event.payload.topic_count,
      }]
    },
    review_required: (event, snap) => {
      planReview.value = { taskId: snap.id, stage: event.payload.stage, topicCount: event.payload.topic_count }
    },
    review_approved: () => {
      planReview.value = null
    },
    citation_review: (event, snap) => {
      citationReview.value = {
        taskId: snap.id,
        mode: event.payload.mode,
        total: event.payload.total,
        counts: { pass: event.payload.pass, flag: event.payload.flag, reject: event.payload.reject },
      }
    },
    done: (event, snap) => {
      snap.final_report = event.payload.final_report
      writerStream.value = event.payload.final_report.markdown || ''
      snap.status = 'done'
    },
    usage: (event, snap) => {
      const cost = event.payload.usage?.cost_usd
      if (cost) snap.cost_usd = (snap.cost_usd || 0) + cost
    },
    cancelled: (_event, snap) => {
      snap.status = 'cancelled'
    },
    error: (event, snap) => {
      snap.status = 'failed'
      error.value = event.payload.error || 'unknown error'
    },
    warning: () => {},
  }

  function applyTypedEvent(event: AthenaEventType, snapshot: TaskSnapshot) {
    const handler = eventHandlers[event.type] as (event: AthenaEventType, snapshot: TaskSnapshot) => void
    handler(event, snapshot)
  }

  function applyEvent(event: StreamEvent) {
    if (!current.value) return
    if (event.task_id !== current.value.id) return
    if (event.seq > 0 && event.seq <= lastSeq.value) return
    if (event.seq > 0) lastSeq.value = event.seq
    events.value.push(event)

    // Re-validate against the typed protocol before applying event-specific
    // state changes through the handler map.
    const parsed = AthenaEvent.safeParse(event)
    if (!parsed.success) return
    applyTypedEvent(parsed.data, current.value)
  }

  function _reset() {
    events.value = []
    writerStream.value = ''
    reviewerNotes.value = []
    supervisorIterations.value = []
    lastExport.value = null
    error.value = null
    lastSeq.value = 0
    citationReview.value = null
    planReview.value = null
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
    citationReview,
    planReview,
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
