import { ofetch, type FetchOptions } from 'ofetch'
import {
  ConfigSnapshot,
  ExportResponse,
  HealthSnapshot,
  StreamEvent,
  TaskSnapshot,
  type ConfigSnapshot as ConfigSnapshotType,
  type ExportResponse as ExportResponseType,
  type HealthSnapshot as HealthSnapshotType,
  type StreamEvent as StreamEventType,
  type TaskSnapshot as TaskSnapshotType,
} from '@/types/api'
import { useSessionStore } from '@/stores/session'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const API_KEY_STORAGE = 'athena.apiKey'

function readApiKey(): string {
  try {
    const direct = localStorage.getItem(API_KEY_STORAGE) || ''
    if (direct) return direct
    const session = useSessionStore()
    return session.apiKey || ''
  } catch {
    return localStorage.getItem(API_KEY_STORAGE) || ''
  }
}

const baseFetch = ofetch.create({
  baseURL: BASE_URL,
  retry: 1,
  retryDelay: 500,
  timeout: 60_000,
  onRequest({ options }) {
    const key = readApiKey()
    if (key) {
      const headers = new Headers(options.headers as HeadersInit | undefined)
      if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${key}`)
      options.headers = headers
    }
  },
})

async function request<T>(path: string, opts: FetchOptions = {}, parser?: { parse: (x: unknown) => T }): Promise<T> {
  const raw = await baseFetch(path, opts)
  return parser ? parser.parse(raw) : (raw as T)
}

export async function getHealth(): Promise<HealthSnapshotType> {
  return request('/health', {}, HealthSnapshot)
}

export async function getConfig(): Promise<ConfigSnapshotType> {
  return request('/v1/config', {}, ConfigSnapshot)
}

export async function createTask(question: string, userId = 'demo-user'): Promise<{ task_id: string; stream_url: string; snapshot: TaskSnapshotType }> {
  const payload = await baseFetch('/v1/research', {
    method: 'POST',
    body: { question, user_id: userId },
  })
  return { ...payload, snapshot: TaskSnapshot.parse(payload.snapshot) }
}

export async function getTask(id: string): Promise<TaskSnapshotType> {
  return request(`/v1/research/${id}`, {}, TaskSnapshot)
}

export async function listTasks(): Promise<TaskSnapshotType[]> {
  const raw = (await baseFetch('/v1/research')) as unknown[]
  return raw.map((x) => TaskSnapshot.parse(x))
}

export async function interruptTask(id: string): Promise<boolean> {
  const resp = await baseFetch(`/v1/research/${id}/interrupt`, { method: 'POST' })
  return Boolean(resp.interrupted)
}

export async function exportReport(id: string, fmt: 'md' | 'html' | 'pdf' | 'docx'): Promise<ExportResponseType> {
  const raw = await baseFetch(`/v1/research/${id}/export`, { method: 'POST', params: { fmt } })
  return ExportResponse.parse(raw)
}

export function buildDownloadUrl(downloadPath: string): string {
  const key = readApiKey()
  const url = new URL(downloadPath, window.location.origin)
  if (key) url.searchParams.set('api_key', key)
  return url.pathname + '?' + url.searchParams.toString()
}

export async function submitFeedback(taskId: string, rating: number, comment = ''): Promise<void> {
  await baseFetch('/v1/feedback', { method: 'POST', body: { task_id: taskId, rating, comment } })
}

// ----- Cost dashboard -----
export interface CostSummary {
  range: string
  start: string
  end: string
  total_cost_usd: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  task_count: number
  avg_cost_per_task: number
}
export interface CostTrend { mode: string; labels: string[]; values: number[] }
export interface CostByModel { total_cost_usd: number; items: { model: string; cost_usd: number; pct: number }[] }
export interface CostByNode { items: { node: string; cost_usd: number; input_tokens: number; output_tokens: number; calls: number }[] }
export interface CostTaskRow { task_id: string; task_name: string; node: string; model: string; calls: number; input_tokens: number; output_tokens: number; cost_usd: number; pct: number; updated_at: string }
export interface CostTip { title: string; desc: string; ico: string; color: string }

export const costApi = {
  summary: (range = 'this-month', taskId?: string): Promise<CostSummary> => baseFetch('/v1/cost/summary', { params: { range, ...(taskId ? { task_id: taskId } : {}) } }),
  trend:   (range = 'this-month', mode: 'day' | 'week' = 'day', taskId?: string): Promise<CostTrend> => baseFetch('/v1/cost/trend', { params: { range, mode, ...(taskId ? { task_id: taskId } : {}) } }),
  byModel: (range = 'this-month', taskId?: string): Promise<CostByModel> => baseFetch('/v1/cost/by-model', { params: { range, ...(taskId ? { task_id: taskId } : {}) } }),
  byNode:  (range = 'this-month', top = 6, taskId?: string): Promise<CostByNode> => baseFetch('/v1/cost/by-node', { params: { range, top, ...(taskId ? { task_id: taskId } : {}) } }),
  tasks:   (range = 'this-month', limit = 20, taskId?: string): Promise<{ items: CostTaskRow[] }> => baseFetch('/v1/cost/tasks', { params: { range, limit, ...(taskId ? { task_id: taskId } : {}) } }),
  tips:    (): Promise<{ items: CostTip[] }> => baseFetch('/v1/cost/tips'),
}

// ----- Citation verification -----
export interface CitationDecision { citation_n: number; status: string; comment: string; decided_by: string; decided_at: string }
export interface CitationListItem { number: number; title: string; url: string; quote: string; decision: CitationDecision | null }

export const citationApi = {
  list: (taskId: string): Promise<{ items: CitationListItem[]; summary: Record<string, number> }> =>
    baseFetch(`/v1/research/${taskId}/citations`),
  verify: (taskId: string, n: number, status: 'pass' | 'reject' | 'flag' | 'replaced', comment = ''): Promise<{ status: string }> =>
    baseFetch(`/v1/research/${taskId}/citations/${n}/verify`, { method: 'POST', body: { status, comment, decided_by: 'human' } }),
}

// ----- Knowledge -----
export interface KnowledgeCollection { id: string; name: string; icon?: string; color?: string; description?: string; created_at: string; updated_at: string }
export interface KnowledgeItem { id: string; collection_id: string | null; name: string; summary?: string; type?: string; source?: string; tags: string[]; usage_count: number; status: string; created_at: string; updated_at: string }
export interface KnowledgeOverview { total_items: number; verified_items: number; verified_pct: number; hot_tags: { label: string; count: number }[]; active_tags: number }

export const knowledgeApi = {
  collections: (): Promise<{ items: KnowledgeCollection[] }> => baseFetch('/v1/knowledge/collections'),
  createCollection: (body: Partial<KnowledgeCollection>): Promise<{ id: string }> =>
    baseFetch('/v1/knowledge/collections', { method: 'POST', body }),
  items: (params: { collection_id?: string; search?: string; status?: string; limit?: number; offset?: number } = {}): Promise<{ items: KnowledgeItem[]; total: number; limit: number; offset: number }> =>
    baseFetch('/v1/knowledge/items', { params }),
  createItem: (body: Partial<KnowledgeItem>): Promise<{ id: string }> =>
    baseFetch('/v1/knowledge/items', { method: 'POST', body }),
  verifyItem: (id: string): Promise<{ id: string; status: string }> =>
    baseFetch(`/v1/knowledge/items/${id}/verify`, { method: 'POST' }),
  deleteItem: (id: string): Promise<{ deleted: string }> =>
    baseFetch(`/v1/knowledge/items/${id}`, { method: 'DELETE' }),
  uploadDocument: async (file: File, collectionId?: string): Promise<{ id: string; filename: string; bytes: number }> => {
    const form = new FormData()
    form.append('file', file)
    const url = `${BASE_URL}/v1/knowledge/upload${collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : ''}`
    const key = readApiKey()
    const headers: Record<string, string> = {}
    if (key) headers.Authorization = `Bearer ${key}`
    const resp = await fetch(url, { method: 'POST', body: form, headers })
    if (!resp.ok) throw new Error(await resp.text())
    return resp.json()
  },
  overview: (): Promise<KnowledgeOverview> => baseFetch('/v1/knowledge/overview'),
  tags: (limit = 20): Promise<{ items: { label: string; count: number }[] }> =>
    baseFetch('/v1/knowledge/tags', { params: { limit } }),
  exportCsvUrl: (params: { collection_id?: string; search?: string; status?: string } = {}): string => {
    const key = readApiKey()
    const u = new URL(`${BASE_URL || window.location.origin}/v1/knowledge/items.csv`)
    Object.entries(params).forEach(([k, v]) => { if (v) u.searchParams.set(k, String(v)) })
    if (key) u.searchParams.set('api_key', key)
    return u.pathname + '?' + u.searchParams.toString()
  },
}

// ----- Misc -----
export interface Announcement { id: string; date: string; title: string; desc: string }
export interface QuickStartLink { label: string; url: string }
export const miscApi = {
  announcements: (limit = 5): Promise<{ items: Announcement[] }> => baseFetch('/v1/announcements', { params: { limit } }),
  quickStart:    (): Promise<{ items: QuickStartLink[] }> => baseFetch('/v1/quick-start'),
}

export async function pauseTask(id: string): Promise<boolean> {
  const resp = await baseFetch(`/v1/research/${id}/pause`, { method: 'POST' })
  return Boolean(resp.interrupted)
}

export interface ReviewBody {
  approved: boolean
  reviewer?: string
  comments?: string
  revised_topics?: { id: string; title: string; question: string; rationale?: string; search_queries: string[]; priority: number }[]
}
export async function submitReview(taskId: string, body: ReviewBody): Promise<{ task_id: string; approved: boolean }> {
  return baseFetch(`/v1/research/${taskId}/review`, {
    method: 'POST',
    body: { task_id: taskId, ...body },
  })
}

/**
 * SSE stream using fetch + ReadableStream so we can attach the Authorization header.
 * EventSource cannot set headers, so we don't use it.
 */
export function openTaskStream(taskId: string, onEvent: (event: StreamEventType) => void, onError?: (err: unknown) => void, signal?: AbortSignal): { close: () => void } {
  const controller = new AbortController()
  if (signal) signal.addEventListener('abort', () => controller.abort())
  const key = readApiKey()
  const url = `${BASE_URL}/v1/research/${taskId}/stream${key ? `?api_key=${encodeURIComponent(key)}` : ''}`

  ;(async () => {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: key ? { Authorization: `Bearer ${key}`, Accept: 'text/event-stream' } : { Accept: 'text/event-stream' },
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        throw new Error(`stream open failed: ${response.status}`)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          for (const line of chunk.split('\n')) {
            if (!line.startsWith('data:')) continue
            const data = line.slice(5).trim()
            if (!data) continue
            try {
              onEvent(StreamEvent.parse(JSON.parse(data)))
            } catch (err) {
              console.warn('[athena] failed to parse SSE event', err, data)
            }
          }
        }
      }
    } catch (err) {
      if ((err as DOMException)?.name === 'AbortError') return
      onError?.(err)
    }
  })()

  return {
    close() {
      controller.abort()
    },
  }
}
