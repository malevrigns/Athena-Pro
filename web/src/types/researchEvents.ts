import { z } from 'zod'

const AnyRecord = z.record(z.string(), z.unknown())
const IsoDateTime = z.string()

export const RESEARCH_EVENT_TYPES = [
  'status',
  'plan_review_required',
  'tool_call',
  'tool_observation',
  'paper_found',
  'claim_extracted',
  'artifact_created',
  'error',
  'done',
] as const

export const ResearchEventType = z.enum(RESEARCH_EVENT_TYPES)
export type ResearchEventType = z.infer<typeof ResearchEventType>

export const PaperScreeningStatus = z.enum(['candidate', 'included', 'excluded', 'read'])
export type PaperScreeningStatus = z.infer<typeof PaperScreeningStatus>

export const Paper = z.object({
  id: z.string().default(''),
  project_id: z.string(),
  title: z.string(),
  authors: z.array(z.string()).default([]),
  year: z.number().int().nullable().optional(),
  venue: z.string().nullable().optional(),
  abstract: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
  pdf_url: z.string().nullable().optional(),
  arxiv_id: z.string().nullable().optional(),
  doi: z.string().nullable().optional(),
  semantic_scholar_id: z.string().nullable().optional(),
  citation_count: z.number().int().nullable().optional(),
  code_url: z.string().nullable().optional(),
  dataset_mentions: z.array(z.string()).default([]),
  screening_status: PaperScreeningStatus.default('candidate'),
  relevance_score: z.number().nullable().optional(),
  created_at: IsoDateTime.optional(),
})
export type Paper = z.infer<typeof Paper>

export const Claim = z.object({
  id: z.string().default(''),
  project_id: z.string(),
  text: z.string(),
  claim_type: z.string(),
  paper_id: z.string().nullable().optional(),
  section: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  evidence_ids: z.array(z.string()).default([]),
  status: z.string().default('draft'),
  created_at: IsoDateTime.optional(),
})
export type Claim = z.infer<typeof Claim>

const ResearchEventBase = z.object({
  task_id: z.string(),
  project_id: z.string().nullable().optional(),
  seq: z.number().int().nonnegative().default(0),
  timestamp: IsoDateTime.optional(),
})

export const StatusPayload = z.object({
  status: z.string(),
  message: z.string().nullable().optional(),
})
export type StatusPayload = z.infer<typeof StatusPayload>

export const PlanReviewRequiredPayload = z.object({
  checkpoint_id: z.string(),
  title: z.string(),
  plan: AnyRecord,
  risk_level: z.string().nullable().optional(),
  estimated_cost_usd: z.number().nullable().optional(),
})
export type PlanReviewRequiredPayload = z.infer<typeof PlanReviewRequiredPayload>

export const ToolCallPayload = z.object({
  tool_call_id: z.string(),
  tool_name: z.string(),
  arguments: AnyRecord,
  permission_level: z.string().nullable().optional(),
  approval_required: z.boolean().default(false),
})
export type ToolCallPayload = z.infer<typeof ToolCallPayload>

export const ToolObservationPayload = z.object({
  tool_call_id: z.string(),
  status: z.string(),
  summary: z.string(),
  structured_output: AnyRecord.default(() => ({})),
  raw_output_ref: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
})
export type ToolObservationPayload = z.infer<typeof ToolObservationPayload>

export const PaperFoundPayload = z.object({
  paper: Paper,
})
export type PaperFoundPayload = z.infer<typeof PaperFoundPayload>

export const ClaimExtractedPayload = z.object({
  claim: Claim,
})
export type ClaimExtractedPayload = z.infer<typeof ClaimExtractedPayload>

export const ArtifactCreatedPayload = z.object({
  artifact_id: z.string(),
  artifact_type: z.string(),
  path: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
})
export type ArtifactCreatedPayload = z.infer<typeof ArtifactCreatedPayload>

export const ErrorPayload = z.object({
  message: z.string(),
  code: z.string().nullable().optional(),
  recoverable: z.boolean().default(true),
})
export type ErrorPayload = z.infer<typeof ErrorPayload>

export const DonePayload = z.object({
  summary: z.string().nullable().optional(),
  final_report_id: z.string().nullable().optional(),
})
export type DonePayload = z.infer<typeof DonePayload>

export const ResearchEvent = z.discriminatedUnion('type', [
  ResearchEventBase.extend({ type: z.literal('status'), payload: StatusPayload }),
  ResearchEventBase.extend({ type: z.literal('plan_review_required'), payload: PlanReviewRequiredPayload }),
  ResearchEventBase.extend({ type: z.literal('tool_call'), payload: ToolCallPayload }),
  ResearchEventBase.extend({ type: z.literal('tool_observation'), payload: ToolObservationPayload }),
  ResearchEventBase.extend({ type: z.literal('paper_found'), payload: PaperFoundPayload }),
  ResearchEventBase.extend({ type: z.literal('claim_extracted'), payload: ClaimExtractedPayload }),
  ResearchEventBase.extend({ type: z.literal('artifact_created'), payload: ArtifactCreatedPayload }),
  ResearchEventBase.extend({ type: z.literal('error'), payload: ErrorPayload }),
  ResearchEventBase.extend({ type: z.literal('done'), payload: DonePayload }),
])
export type ResearchEvent = z.infer<typeof ResearchEvent>

