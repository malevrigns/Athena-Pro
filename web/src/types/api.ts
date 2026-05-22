import { z } from 'zod'

export const TaskStatus = z.enum(['created', 'planning', 'waiting_review', 'researching', 'quality_gate', 'writing', 'done', 'failed', 'cancelled'])
export type TaskStatus = z.infer<typeof TaskStatus>

export const Source = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  snippet: z.string().optional(),
  credibility: z.number().optional(),
  source_type: z.string().optional(),
})
export type Source = z.infer<typeof Source>

export const Finding = z.object({
  id: z.string(),
  topic_id: z.string(),
  title: z.string(),
  summary: z.string(),
  evidence: z.array(z.string()).default([]),
  sources: z.array(Source).default([]),
  confidence: z.number().default(0),
})
export type Finding = z.infer<typeof Finding>

export const ResearchTopic = z.object({
  id: z.string(),
  title: z.string(),
  question: z.string(),
  rationale: z.string().optional(),
  search_queries: z.array(z.string()).default([]),
  priority: z.number().default(1),
})
export type ResearchTopic = z.infer<typeof ResearchTopic>

export const ResearchPlan = z.object({
  id: z.string(),
  question: z.string(),
  topics: z.array(ResearchTopic),
  assumptions: z.array(z.string()).default([]),
  success_criteria: z.array(z.string()).default([]),
  estimated_cost_usd: z.number().default(0),
})
export type ResearchPlan = z.infer<typeof ResearchPlan>

export const QualityScore = z.object({
  factuality: z.number().default(0),
  coverage: z.number().default(0),
  citation_integrity: z.number().default(0),
  contradiction_risk: z.number().default(0),
  overall: z.number().default(0),
  notes: z.array(z.string()).default([]),
})
export type QualityScore = z.infer<typeof QualityScore>

export const Citation = z.object({
  number: z.number(),
  source_id: z.string(),
  title: z.string(),
  url: z.string(),
  quote: z.string().optional(),
})
export type Citation = z.infer<typeof Citation>

export const FinalReport = z.object({
  task_id: z.string(),
  title: z.string(),
  markdown: z.string(),
  citations: z.array(Citation).default([]),
  quality: QualityScore.nullish(),
})
export type FinalReport = z.infer<typeof FinalReport>

export const TaskSnapshot = z.object({
  id: z.string(),
  question: z.string(),
  user_id: z.string(),
  status: TaskStatus,
  plan: ResearchPlan.nullish(),
  findings: z.array(Finding).default([]),
  final_report: FinalReport.nullish(),
  quality: QualityScore.nullish(),
  cost_usd: z.number().default(0),
  events_count: z.number().default(0),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
})
export type TaskSnapshot = z.infer<typeof TaskSnapshot>

// Loose runtime carrier — used by components that render events generically.
export const StreamEvent = z.object({
  seq: z.number().default(0),
  type: z.string(),
  task_id: z.string(),
  node: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).default({}),
  ts: z.string().optional(),
})
export type StreamEvent = z.infer<typeof StreamEvent>

// ---- Typed event protocol -------------------------------------------------
// Hand-written 1:1 mirror of the backend `AthenaEvent` discriminated union
// (src/athena/schemas.py). Payloads stay lenient (.passthrough(), defaults) so
// a valid event is never dropped; only `type` is strict.
const eventBase = {
  seq: z.number().default(0),
  task_id: z.string(),
  node: z.string().nullable().optional(),
  ts: z.string().optional(),
}
const UsageEntry = z.object({
  node: z.string().optional(),
  model: z.string().optional(),
  input_tokens: z.number().optional(),
  output_tokens: z.number().optional(),
  cost_usd: z.number().optional(),
}).passthrough()

export const AthenaEvent = z.discriminatedUnion('type', [
  z.object({ ...eventBase, type: z.literal('created'),
    payload: z.object({ question: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('status'),
    payload: z.object({ status: TaskStatus, updated_at: z.string().optional() }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('plan'),
    payload: z.object({ plan: ResearchPlan }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('plan_expanded'),
    payload: z.object({ new_topics: z.array(ResearchTopic).default([]) }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('finding'),
    payload: z.object({ finding: Finding }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('quality'),
    payload: z.object({ quality: QualityScore }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('review'),
    payload: z.object({ review: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('route'),
    payload: z.object({
      iteration: z.number().default(0),
      route: z.string().default(''),
      quality: z.number().nullish(),
      finding_count: z.number().default(0),
      topic_count: z.number().default(0),
    }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('done'),
    payload: z.object({ final_report: FinalReport }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('usage'),
    payload: z.object({ usage: UsageEntry.optional() }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('cancelled'),
    payload: z.object({ reason: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('error'),
    payload: z.object({ error: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('warning'),
    payload: z.object({ message: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('review_required'),
    payload: z.object({
      stage: z.string().default('plan'),
      topic_count: z.number().default(0),
      message: z.string().default(''),
    }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('review_approved'),
    payload: z.object({ comments: z.string().default('') }).passthrough() }),
  z.object({ ...eventBase, type: z.literal('citation_review'),
    payload: z.object({
      mode: z.string().default('manual'),
      total: z.number().default(0),
      pending: z.number().default(0),
      model: z.string().default(''),
      message: z.string().default(''),
      pass: z.number().default(0),
      flag: z.number().default(0),
      reject: z.number().default(0),
    }).passthrough() }),
])
export type AthenaEvent = z.infer<typeof AthenaEvent>

export const ConfigSnapshot = z.object({
  env: z.string(),
  llm_provider: z.string(),
  default_model: z.string(),
  search_provider: z.string(),
  quality_threshold: z.number(),
  max_research_iterations: z.number(),
  max_budget_usd: z.number(),
  require_auth: z.boolean(),
  export_formats: z.record(z.string(), z.boolean()),
  has_openai_key: z.boolean(),
  has_anthropic_key: z.boolean(),
  has_tavily_key: z.boolean(),
  has_gemma_key: z.boolean().default(false),
})
export type ConfigSnapshot = z.infer<typeof ConfigSnapshot>

export const HealthSnapshot = z.object({
  ok: z.boolean(),
  version: z.string(),
  uptime_sec: z.number(),
  llm_provider: z.string(),
  search_provider: z.string(),
  db_path: z.string(),
  extras: z.record(z.string(), z.unknown()).optional(),
})
export type HealthSnapshot = z.infer<typeof HealthSnapshot>

export const ExportResponse = z.object({
  task_id: z.string(),
  format: z.string(),
  filename: z.string(),
  bytes: z.number(),
  download_url: z.string(),
})
export type ExportResponse = z.infer<typeof ExportResponse>
