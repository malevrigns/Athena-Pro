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

export const StreamEvent = z.object({
  type: z.string(),
  task_id: z.string(),
  node: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).default({}),
  ts: z.string().optional(),
})
export type StreamEvent = z.infer<typeof StreamEvent>

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
