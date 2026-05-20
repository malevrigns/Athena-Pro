import { z } from 'zod'

// SSE 事件用 discriminated union,每种 type 字段集不同
export const SseEvent = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('connected'),
    task_id: z.string(),
  }),
  z.object({
    type: z.literal('node_update'),
    node: z.string(),
    summary: z.object({
      type: z.string(),
      preview: z.string().optional(),
      count: z.number().optional(),
    }).passthrough(),
  }),
  z.object({
    type: z.literal('token'),
    node: z.string().nullable(),
    content: z.string(),
  }),
  z.object({
    type: z.literal('plan_review_required'),
    plan: z.object({
      topics: z.array(z.string()),
      rationale: z.string(),
    }),
    deadline_sec: z.number(),
  }),
  z.object({
    type: z.literal('permission_required'),
    request_id: z.string(),
    tool_name: z.string(),
    args: z.record(z.unknown()),
    risk_level: z.enum(['low', 'medium', 'high']),
    reason: z.string(),
  }),
  z.object({
    type: z.literal('done'),
    final_report: z.string().nullable(),
    metadata: z.record(z.unknown()).optional(),
  }),
  z.object({
    type: z.literal('error'),
    error: z.string(),
  }),
])
export type SseEvent = z.infer