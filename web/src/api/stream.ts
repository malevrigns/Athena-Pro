import { buildApiUrl, readApiKey } from '@/api/client'
import { StreamEvent, type StreamEvent as StreamEventType } from '@/types/api'

/**
 * SSE stream using fetch + ReadableStream so Authorization headers are available.
 */
export function openTaskStream(
  taskId: string,
  onEvent: (event: StreamEventType) => void,
  onError?: (err: unknown) => void,
  signal?: AbortSignal,
  afterSeq = 0,
): { close: () => void } {
  const controller = new AbortController()
  if (signal) signal.addEventListener('abort', () => controller.abort())
  const query = afterSeq > 0 ? `?after_seq=${encodeURIComponent(String(afterSeq))}` : ''
  const url = buildApiUrl(`/v1/research/${taskId}/stream${query}`)

  ;(async () => {
    try {
      await pumpTaskStream(url, readApiKey(), controller.signal, onEvent)
    } catch (err) {
      if ((err as DOMException)?.name === 'AbortError') return
      onError?.(err)
    }
  })()

  return {
    close() {
      controller.abort()
    },
  }
}

async function pumpTaskStream(
  url: string,
  key: string,
  signal: AbortSignal,
  onEvent: (event: StreamEventType) => void,
): Promise<void> {
  const response = await fetch(url, {
    method: 'GET',
    headers: streamHeaders(key),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`stream open failed: ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer = consumeSseBuffer(buffer + decoder.decode(value, { stream: true }), onEvent)
  }
}

function streamHeaders(key: string): HeadersInit {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (key) headers.Authorization = `Bearer ${key}`
  return headers
}

function consumeSseBuffer(buffer: string, onEvent: (event: StreamEventType) => void): string {
  let rest = buffer
  let idx: number
  while ((idx = rest.indexOf('\n\n')) !== -1) {
    emitSseChunk(rest.slice(0, idx), onEvent)
    rest = rest.slice(idx + 2)
  }
  return rest
}

function emitSseChunk(chunk: string, onEvent: (event: StreamEventType) => void): void {
  for (const line of chunk.split('\n')) {
    if (!line.startsWith('data:')) continue
    const data = line.slice(5).trim()
    if (!data) continue
    try {
      const raw = JSON.parse(data)
      if (!raw.type || !raw.task_id) continue
      onEvent(StreamEvent.parse(raw))
    } catch (err) {
      console.warn('[athena] failed to parse SSE event', err, data)
    }
  }
}
