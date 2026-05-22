import { ofetch, type FetchOptions } from 'ofetch'
import {
  ConfigSnapshot,
  ExportResponse,
  HealthSnapshot,
  TaskSnapshot,
  type ConfigSnapshot as ConfigSnapshotType,
  type ExportResponse as ExportResponseType,
  type HealthSnapshot as HealthSnapshotType,
  type TaskSnapshot as TaskSnapshotType,
} from '@/types/api'
import {
  Paper,
  PaperNote,
  ResearchProject,
  ToolResult,
  ToolTraceItem,
  type CreatePaperInput,
  type CreatePaperNoteInput,
  type CreateResearchProjectInput,
  type Paper as PaperType,
  type PaperNote as PaperNoteType,
  type ResearchProject as ResearchProjectType,
  type ToolResult as ToolResultType,
  type ToolTraceItem as ToolTraceItemType,
} from '@/types/research'
import { useSessionStore } from '@/stores/session'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const API_KEY_STORAGE = 'athena.apiKey'
const API_BASE_STORAGE = 'athena.apiBase'

export function readApiKey(): string {
  try {
    const direct = localStorage.getItem(API_KEY_STORAGE) || ''
    if (direct) return direct
    const session = useSessionStore()
    return session.apiKey || ''
  } catch {
    return localStorage.getItem(API_KEY_STORAGE) || ''
  }
}

function readApiBase(): string {
  try {
    const session = useSessionStore()
    return session.apiBase || localStorage.getItem(API_BASE_STORAGE) || BASE_URL
  } catch {
    return localStorage.getItem(API_BASE_STORAGE) || BASE_URL
  }
}

export function buildApiUrl(path: string): string {
  const base = readApiBase()
  if (!base) return path
  return new URL(path, base).toString()
}

const baseFetch = ofetch.create({
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

export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  return baseFetch(buildApiUrl(path), opts) as unknown as Promise<T>
}

async function request<T>(path: string, opts: FetchOptions = {}, parser?: { parse: (x: unknown) => T }): Promise<T> {
  const raw = await apiFetch(path, opts)
  return parser ? parser.parse(raw) : (raw as T)
}

export async function getHealth(): Promise<HealthSnapshotType> {
  return request('/health', {}, HealthSnapshot)
}

export async function getConfig(): Promise<ConfigSnapshotType> {
  return request('/v1/config', {}, ConfigSnapshot)
}

export async function createTask(question: string, userId = 'demo-user'): Promise<{ task_id: string; stream_url: string; snapshot: TaskSnapshotType }> {
  const payload = await apiFetch<{ task_id: string; stream_url: string; snapshot: unknown }>('/v1/research', {
    method: 'POST',
    body: { question, user_id: userId },
  })
  return { ...payload, snapshot: TaskSnapshot.parse(payload.snapshot) }
}

export async function getTask(id: string): Promise<TaskSnapshotType> {
  return request(`/v1/research/${id}`, {}, TaskSnapshot)
}

export async function listTasks(): Promise<TaskSnapshotType[]> {
  const raw = (await apiFetch('/v1/research')) as unknown[]
  return raw.map((x) => TaskSnapshot.parse(x))
}

export async function interruptTask(id: string): Promise<boolean> {
  const resp = await apiFetch<{ interrupted: boolean }>(`/v1/research/${id}/interrupt`, { method: 'POST' })
  return Boolean(resp.interrupted)
}

export async function exportReport(id: string, fmt: 'md' | 'html' | 'pdf' | 'docx'): Promise<ExportResponseType> {
  const raw = await apiFetch(`/v1/research/${id}/export`, { method: 'POST', params: { fmt } })
  return ExportResponse.parse(raw)
}

export async function downloadFile(downloadPath: string, filename: string): Promise<string> {
  const response = await authorizedFetch(downloadPath)
  const blobUrl = URL.createObjectURL(await response.blob())
  triggerDownload(blobUrl, filename)
  return blobUrl
}

async function authorizedFetch(path: string): Promise<Response> {
  const key = readApiKey()
  const headers = key ? { Authorization: `Bearer ${key}` } : undefined
  const response = await fetch(buildApiUrl(path), { headers })
  if (!response.ok) throw new Error(await response.text())
  return response
}

function triggerDownload(url: string, filename: string): void {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export async function submitFeedback(taskId: string, rating: number, comment = ''): Promise<void> {
  await apiFetch('/v1/feedback', { method: 'POST', body: { task_id: taskId, rating, comment } })
}

// ----- Research OS projects -----
export const projectApi = {
  create: (body: CreateResearchProjectInput): Promise<ResearchProjectType> =>
    request('/v1/projects', { method: 'POST', body }, ResearchProject),
  list: async (limit = 50): Promise<ResearchProjectType[]> => {
    const raw = await apiFetch<unknown[]>('/v1/projects', { params: { limit } })
    return raw.map((item) => ResearchProject.parse(item))
  },
  get: (projectId: string): Promise<ResearchProjectType> =>
    request(`/v1/projects/${projectId}`, {}, ResearchProject),
  createPaper: (projectId: string, body: CreatePaperInput): Promise<PaperType> =>
    request(`/v1/projects/${projectId}/papers`, { method: 'POST', body }, Paper),
  listPapers: async (projectId: string, params: { limit?: number; screening_status?: string } = {}): Promise<PaperType[]> => {
    const raw = await apiFetch<unknown[]>(`/v1/projects/${projectId}/papers`, { params })
    return raw.map((item) => Paper.parse(item))
  },
  getPaper: (projectId: string, paperId: string): Promise<PaperType> =>
    request(`/v1/projects/${projectId}/papers/${paperId}`, {}, Paper),
  searchPapers: (projectId: string, body: { query: string; limit?: number; task_id?: string }): Promise<ToolResultType> =>
    request(`/v1/projects/${projectId}/paper-search`, { method: 'POST', body }, ToolResult),
  extractPaperNote: (projectId: string, paperId: string, body: { task_id?: string } = {}): Promise<ToolResultType> =>
    request(`/v1/projects/${projectId}/papers/${paperId}/note-extract`, { method: 'POST', body }, ToolResult),
  createPaperNote: (projectId: string, paperId: string, body: CreatePaperNoteInput): Promise<PaperNoteType> =>
    request(`/v1/projects/${projectId}/papers/${paperId}/notes`, { method: 'POST', body }, PaperNote),
  listPaperNotes: async (projectId: string, paperId: string): Promise<PaperNoteType[]> => {
    const raw = await apiFetch<unknown[]>(`/v1/projects/${projectId}/papers/${paperId}/notes`)
    return raw.map((item) => PaperNote.parse(item))
  },
  trace: async (projectId: string): Promise<ToolTraceItemType[]> => {
    const raw = await apiFetch<unknown[]>(`/v1/projects/${projectId}/trace`)
    return raw.map((item) => ToolTraceItem.parse(item))
  },
  taskTrace: async (taskId: string): Promise<ToolTraceItemType[]> => {
    const raw = await apiFetch<unknown[]>(`/v1/research/${taskId}/trace`)
    return raw.map((item) => ToolTraceItem.parse(item))
  },
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
  summary: (range = 'this-month', taskId?: string): Promise<CostSummary> => apiFetch('/v1/cost/summary', { params: { range, ...(taskId ? { task_id: taskId } : {}) } }),
  trend:   (range = 'this-month', mode: 'day' | 'week' = 'day', taskId?: string): Promise<CostTrend> => apiFetch('/v1/cost/trend', { params: { range, mode, ...(taskId ? { task_id: taskId } : {}) } }),
  byModel: (range = 'this-month', taskId?: string): Promise<CostByModel> => apiFetch('/v1/cost/by-model', { params: { range, ...(taskId ? { task_id: taskId } : {}) } }),
  byNode:  (range = 'this-month', top = 6, taskId?: string): Promise<CostByNode> => apiFetch('/v1/cost/by-node', { params: { range, top, ...(taskId ? { task_id: taskId } : {}) } }),
  tasks:   (range = 'this-month', limit = 20, taskId?: string): Promise<{ items: CostTaskRow[] }> => apiFetch('/v1/cost/tasks', { params: { range, limit, ...(taskId ? { task_id: taskId } : {}) } }),
  tips:    (): Promise<{ items: CostTip[] }> => apiFetch('/v1/cost/tips'),
  downloadTasksCsv: async (range = 'this-month', taskId?: string): Promise<void> => {
    const query = new URLSearchParams({ range })
    if (taskId) query.set('task_id', taskId)
    const response = await authorizedFetch(`/v1/cost/tasks.csv?${query.toString()}`)
    const url = URL.createObjectURL(await response.blob())
    triggerDownload(url, 'cost-tasks.csv')
  },
}

// ----- Citation verification -----
export interface CitationDecision { citation_n: number; status: string; comment: string; decided_by: string; decided_at: string }
export interface CitationListItem { number: number; title: string; url: string; quote: string; decision: CitationDecision | null }

export const citationApi = {
  list: (taskId: string): Promise<{ items: CitationListItem[]; summary: Record<string, number> }> =>
    apiFetch(`/v1/research/${taskId}/citations`),
  verify: (taskId: string, n: number, status: 'pass' | 'reject' | 'flag' | 'replaced', comment = ''): Promise<{ status: string }> =>
    apiFetch(`/v1/research/${taskId}/citations/${n}/verify`, { method: 'POST', body: { status, comment, decided_by: 'human' } }),
}

// ----- Citation verification settings (server-global) -----
export interface VerifierConfig { provider: string; model: string; base_url: string; has_api_key: boolean }
export interface CitationSettings { manual_review: boolean; verifier: VerifierConfig }
export interface VerifierUpdate { provider: string; model: string; base_url: string; api_key?: string }
export interface VerifierTestResult { ok: boolean; model?: string; sample?: string; detail?: string }

export const settingsApi = {
  get: (): Promise<CitationSettings> => apiFetch('/v1/settings'),
  update: (body: { manual_review: boolean; verifier: VerifierUpdate }): Promise<CitationSettings> =>
    apiFetch('/v1/settings', { method: 'PUT', body }),
  testVerifier: (): Promise<VerifierTestResult> =>
    apiFetch('/v1/settings/verifier/test', { method: 'POST' }),
}

// ----- Knowledge -----
export interface KnowledgeCollection { id: string; name: string; icon?: string; color?: string; description?: string; created_at: string; updated_at: string }
export interface KnowledgeItem { id: string; collection_id: string | null; name: string; summary?: string; type?: string; source?: string; tags: string[]; usage_count: number; status: string; created_at: string; updated_at: string }
export interface KnowledgeOverview { total_items: number; verified_items: number; verified_pct: number; hot_tags: { label: string; count: number }[]; active_tags: number }

export const knowledgeApi = {
  collections: (): Promise<{ items: KnowledgeCollection[] }> => apiFetch('/v1/knowledge/collections'),
  createCollection: (body: Partial<KnowledgeCollection>): Promise<{ id: string }> =>
    apiFetch('/v1/knowledge/collections', { method: 'POST', body }),
  items: (params: { collection_id?: string; search?: string; status?: string; limit?: number; offset?: number } = {}): Promise<{ items: KnowledgeItem[]; total: number; limit: number; offset: number }> =>
    apiFetch('/v1/knowledge/items', { params }),
  createItem: (body: Partial<KnowledgeItem>): Promise<{ id: string }> =>
    apiFetch('/v1/knowledge/items', { method: 'POST', body }),
  verifyItem: (id: string): Promise<{ id: string; status: string }> =>
    apiFetch(`/v1/knowledge/items/${id}/verify`, { method: 'POST' }),
  deleteItem: (id: string): Promise<{ deleted: string }> =>
    apiFetch(`/v1/knowledge/items/${id}`, { method: 'DELETE' }),
  uploadDocument: async (file: File, collectionId?: string): Promise<{ id: string; filename: string; bytes: number }> => {
    const form = new FormData()
    form.append('file', file)
    const path = `/v1/knowledge/upload${collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : ''}`
    const key = readApiKey()
    const headers: Record<string, string> = {}
    if (key) headers.Authorization = `Bearer ${key}`
    const resp = await fetch(buildApiUrl(path), { method: 'POST', body: form, headers })
    if (!resp.ok) throw new Error(await resp.text())
    return resp.json()
  },
  overview: (): Promise<KnowledgeOverview> => apiFetch('/v1/knowledge/overview'),
  tags: (limit = 20): Promise<{ items: { label: string; count: number }[] }> =>
    apiFetch('/v1/knowledge/tags', { params: { limit } }),
  downloadCsv: async (params: { collection_id?: string; search?: string; status?: string } = {}): Promise<void> => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => { if (value) query.set(key, String(value)) })
    const suffix = query.toString() ? `?${query.toString()}` : ''
    const response = await authorizedFetch(`/v1/knowledge/items.csv${suffix}`)
    triggerDownload(URL.createObjectURL(await response.blob()), 'knowledge.csv')
  },
}

// ----- Misc -----
export interface Announcement { id: string; date: string; title: string; desc: string }
export interface QuickStartLink { label: string; url: string }
export const miscApi = {
  announcements: (limit = 5): Promise<{ items: Announcement[] }> => apiFetch('/v1/announcements', { params: { limit } }),
  quickStart:    (): Promise<{ items: QuickStartLink[] }> => apiFetch('/v1/quick-start'),
}

export interface NotificationItem {
  id: string
  kind: string
  title: string
  desc: string
  level: string
  task_id: string
  route: string
  created_at: string
}
export const notificationApi = {
  list: (limit = 20): Promise<{ items: NotificationItem[]; unread: number }> =>
    apiFetch('/v1/notifications', { params: { limit } }),
}

export interface AuditEvent {
  id: string
  type: 'plan_review' | 'citation_verification'
  title: string
  status: string
  actor: string
  task_id: string
  route: string
  created_at: string
  detail: string
}
export const auditApi = {
  events: (limit = 20): Promise<{ items: AuditEvent[]; total: number }> =>
    apiFetch('/v1/audit/events', { params: { limit } }),
}

export async function pauseTask(id: string): Promise<boolean> {
  const resp = await apiFetch<{ interrupted: boolean }>(`/v1/research/${id}/pause`, { method: 'POST' })
  return Boolean(resp.interrupted)
}

export interface ReviewBody {
  approved: boolean
  reviewer?: string
  comments?: string
  revised_topics?: { id: string; title: string; question: string; rationale?: string; search_queries: string[]; priority: number }[]
}
export async function submitReview(taskId: string, body: ReviewBody): Promise<{ task_id: string; approved: boolean }> {
  return apiFetch(`/v1/research/${taskId}/review`, {
    method: 'POST',
    body: { task_id: taskId, ...body },
  })
}
