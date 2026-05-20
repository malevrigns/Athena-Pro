import { apiClient } from './client'

export type Scope = 'once' | 'session' | 'forever'
export type RiskLevel = 'low' | 'medium' | 'high'

export interface PermissionRequest {
  request_id: string
  task_id: string
  tool_name: string
  args: Record<string, any>
  risk_level: RiskLevel
  reason: string
}

export interface PermissionDecisionRecord {
  id: string
  tool_name: string
  scope: Scope
  decision: 'allow' | 'deny'
  created_at: string
}

export const permissionApi = {
  /** 提交一次决策(继续 / 拒绝 + 范围) */
  decide(requestId: string, body: { action: 'allow' | 'deny'; scope: Scope }) {
    return apiClient.post(`/v1/permissions/decisions/${requestId}`, body)
  },

  /** 列出当前用户所有授权(session + forever) */
  list() {
    return apiClient.get<PermissionDecisionRecord[]>('/v1/permissions')
  },

  /** 撤回一条授权 */
  revoke(decisionId: string) {
    return apiClient.delete(`/v1/permissions/${decisionId}`)
  },

  /** 清空所有 session 级授权(用户退出会话时调) */
  clearSession() {
    return apiClient.delete('/v1/permissions?scope=session')
  },
}