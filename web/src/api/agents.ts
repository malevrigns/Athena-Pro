import { apiFetch } from '@/api/client'

export type AgentTraceStatus = 'queued' | 'running' | 'done' | 'skipped' | 'failed'

export interface AgentTraceItem {
  id: string
  role: string
  title: string
  status: AgentTraceStatus
  objective: string
  input_summary: string
  output_summary: string
  evidence_count: number
  source_count: number
  knowledge_hits: number
  token_count: number
  cost_usd: number
  autonomy_level: string
  capabilities: string[]
  tools: string[]
  next_action: string
  updated_at: string
}

export interface AgentTraceSummary {
  total_agents: number
  completed_agents: number
  running_agents: number
  queued_agents: number
  skipped_agents: number
  failed_agents: number
  source_count: number
  knowledge_hits: number
  total_tokens: number
  total_cost_usd: number
  capability_count: number
  tool_count: number
}

export interface AgentTraceResponse {
  items: AgentTraceItem[]
  summary: AgentTraceSummary
}

export const agentApi = {
  trace: (taskId: string): Promise<AgentTraceResponse> => apiFetch(`/v1/research/${taskId}/agents`),
}
