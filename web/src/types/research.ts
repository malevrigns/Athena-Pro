import { z } from 'zod'

export const ProjectStatus = z.enum([
  'draft',
  'planning',
  'running',
  'waiting_review',
  'completed',
  'failed',
  'cancelled',
])
export type ProjectStatus = z.infer<typeof ProjectStatus>

export const ResearchProject = z.object({
  id: z.string(),
  title: z.string(),
  research_question: z.string(),
  field: z.string().nullable().optional(),
  constraints: z.array(z.string()).default([]),
  target_venue: z.string().nullable().optional(),
  status: ProjectStatus,
  owner: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
})
export type ResearchProject = z.infer<typeof ResearchProject>

export const CreateResearchProjectInput = z.object({
  title: z.string().min(1),
  research_question: z.string().min(3),
  field: z.string().nullable().optional(),
  constraints: z.array(z.string()).default([]),
  target_venue: z.string().nullable().optional(),
  owner: z.string().nullable().optional(),
})
export type CreateResearchProjectInput = z.infer<typeof CreateResearchProjectInput>

export const PaperScreeningStatus = z.enum(['candidate', 'included', 'excluded', 'read'])
export type PaperScreeningStatus = z.infer<typeof PaperScreeningStatus>

export const Paper = z.object({
  id: z.string(),
  project_id: z.string(),
  title: z.string(),
  authors: z.array(z.string()).default([]),
  year: z.number().nullable().optional(),
  venue: z.string().nullable().optional(),
  abstract: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
  pdf_url: z.string().nullable().optional(),
  arxiv_id: z.string().nullable().optional(),
  doi: z.string().nullable().optional(),
  semantic_scholar_id: z.string().nullable().optional(),
  citation_count: z.number().nullable().optional(),
  code_url: z.string().nullable().optional(),
  dataset_mentions: z.array(z.string()).default([]),
  screening_status: PaperScreeningStatus,
  relevance_score: z.number().nullable().optional(),
  created_at: z.string(),
})
export type Paper = z.infer<typeof Paper>

export const CreatePaperInput = z.object({
  title: z.string().min(1),
  authors: z.array(z.string()).default([]),
  year: z.number().nullable().optional(),
  venue: z.string().nullable().optional(),
  abstract: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
  pdf_url: z.string().nullable().optional(),
  arxiv_id: z.string().nullable().optional(),
  doi: z.string().nullable().optional(),
  semantic_scholar_id: z.string().nullable().optional(),
  citation_count: z.number().nullable().optional(),
  code_url: z.string().nullable().optional(),
  dataset_mentions: z.array(z.string()).default([]),
  screening_status: PaperScreeningStatus.default('candidate'),
  relevance_score: z.number().nullable().optional(),
})
export type CreatePaperInput = z.infer<typeof CreatePaperInput>

export const PaperNote = z.object({
  id: z.string(),
  paper_id: z.string(),
  problem: z.string().nullable().optional(),
  method: z.string().nullable().optional(),
  training_setup: z.string().nullable().optional(),
  datasets: z.array(z.string()).default([]),
  metrics: z.array(z.string()).default([]),
  baselines: z.array(z.string()).default([]),
  main_results: z.string().nullable().optional(),
  limitations: z.string().nullable().optional(),
  reproducibility_notes: z.string().nullable().optional(),
  important_sections: z.array(z.string()).default([]),
  created_at: z.string(),
})
export type PaperNote = z.infer<typeof PaperNote>

export const CreatePaperNoteInput = z.object({
  problem: z.string().nullable().optional(),
  method: z.string().nullable().optional(),
  training_setup: z.string().nullable().optional(),
  datasets: z.array(z.string()).default([]),
  metrics: z.array(z.string()).default([]),
  baselines: z.array(z.string()).default([]),
  main_results: z.string().nullable().optional(),
  limitations: z.string().nullable().optional(),
  reproducibility_notes: z.string().nullable().optional(),
  important_sections: z.array(z.string()).default([]),
})
export type CreatePaperNoteInput = z.infer<typeof CreatePaperNoteInput>

export const PermissionLevel = z.enum([
  'read_only',
  'network_read',
  'write_artifact',
  'write_repo',
  'run_local_command',
  'run_expensive_job',
  'external_side_effect',
  'destructive',
])
export type PermissionLevel = z.infer<typeof PermissionLevel>

export const ToolCallStatus = z.enum([
  'pending',
  'waiting_approval',
  'running',
  'completed',
  'failed',
  'skipped',
])
export type ToolCallStatus = z.infer<typeof ToolCallStatus>

export const ToolObservationStatus = z.enum(['ok', 'error', 'skipped'])
export type ToolObservationStatus = z.infer<typeof ToolObservationStatus>

export const ToolCallRecord = z.object({
  id: z.string(),
  task_id: z.string(),
  tool_name: z.string(),
  arguments: z.record(z.string(), z.unknown()).default({}),
  project_id: z.string().nullable().optional(),
  permission_level: PermissionLevel,
  approval_status: z.string(),
  status: ToolCallStatus,
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
})
export type ToolCallRecord = z.infer<typeof ToolCallRecord>

export const ToolObservationRecord = z.object({
  id: z.string(),
  tool_call_id: z.string(),
  status: ToolObservationStatus,
  summary: z.string(),
  structured_output: z.record(z.string(), z.unknown()).default({}),
  raw_output_ref: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
  created_at: z.string(),
})
export type ToolObservationRecord = z.infer<typeof ToolObservationRecord>

export const ToolResult = z.object({
  ok: z.boolean(),
  summary: z.string(),
  structured_output: z.record(z.string(), z.unknown()).default({}),
  raw_output_ref: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
})
export type ToolResult = z.infer<typeof ToolResult>

export const ToolTraceItem = z.object({
  call: ToolCallRecord,
  observations: z.array(ToolObservationRecord).default([]),
})
export type ToolTraceItem = z.infer<typeof ToolTraceItem>
