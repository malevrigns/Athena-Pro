import { useSessionStore } from '@/stores/session'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface FetchOptions extends Omit {
  body?: unknown                                  // 自动 JSON.stringify
  timeout?: number                                // 默认 30s,可覆盖
}

export async function http(
  path: string,
  options: FetchOptions = {},
): Promise {
  const session = useSessionStore()
  const { timeout = 30_000, body, headers, ...rest } = options
  
  // 1. 拼 URL
  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`
  
  // 2. 注入认证 header
  const finalHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    ...headers,
  }
  if (session.token) {
    (finalHeaders as Record).Authorization = `Bearer ${session.token}`
  }
  
  // 3. 超时控制 · 用 AbortController
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  
  try {
    const res = await fetch(url, {
      ...rest,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    
    if (!res.ok) {
      // 统一错误处理:把 HTTP error 转成 ApiError
      let errBody: { code?: string; message?: string; details?: unknown } = {}
      try { errBody = await res.json() } catch {}
      
      // 401 → session 失效,登出
      if (res.status === 401) {
        session.logout()
      }
      
      throw new ApiError(
        res.status,
        errBody.code ?? 'http_error',
        errBody.message ?? `HTTP ${res.status}`,
        errBody.details,
      )
    }
    
    // 204 No Content
    if (res.status === 204) return undefined as T
    
    return await res.json() as T
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      throw new ApiError(0, 'timeout', `请求超时(${timeout}ms)`)
    }
    throw e
  } finally {
    clearTimeout(timeoutId)
  }
}