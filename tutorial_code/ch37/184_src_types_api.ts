import { z } from 'zod'

// ===== 任务相关 =====
export const CreateTaskRequest = z.object({
  question: z.string().min(10).max(500),
  user_id: z.string().nullable().optional(),
})
export type CreateTaskRequest = z.infer

export const CreateTaskResponse = z.object({
  task_id: z.string(),
  stream_url: z.string(),
})
export type CreateTaskResponse = z.infer

export const TaskStatus = z.enum(['pending', 'running', 'done', 'aborted', 'failed'])
export type TaskStatus = z.infer

export const TaskSummary = z.object({
  task_id: z.string(),
  question: z.string(),
  status: TaskStatus,
  cost_usd: z.number(),
  created_at: z.string(),
  completed_at: z.string().nullable(),
})
export type TaskSummary = z.infer

// ===== Citation =====
export const Citation = z.object({
  number: z.number(),
  title: z.string(),
  url: z.string(),
  snippet: z.string(),
  fetched_at: z.string().optional(),
})
export type Citation = z.infer

// ===== Cost =====
export const CostInfo = z.object({
  spent_usd: z.number(),
  budget_usd: z.number(),
  by_model: z.record(z.number()),
  by_node: z.record(z.number()),
  n_llm_calls: z.number(),
})
export type CostInfo = z.infer