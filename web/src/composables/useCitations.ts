import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { citationApi, type CitationDecision, type CitationListItem } from '@/api/client'
import type { Citation } from '@/types/api'

export interface CiteRow {
  n: number
  body: string
  status: 'pass' | 'wait' | 'low'
  conf: number
  risk: 'low' | 'mid' | 'high'
  citation: Citation
  decision: CitationDecision | null
}

export function sourceHost(c: Citation): string {
  try {
    return new URL(c.url).hostname
  } catch {
    return ''
  }
}

// Heuristic confidence/risk score for a citation, before any human decision.
function classify(c: Citation): { status: 'pass' | 'wait' | 'low'; conf: number; risk: 'low' | 'mid' | 'high' } {
  const isMock = c.url.startsWith('https://example.com')
  const trusted = /idc|gartner|mckinsey|forrester|bcg|nature|arxiv|stanford/i.test(c.url + c.title)
  let conf = trusted ? 0.85 : isMock ? 0.40 : 0.62
  conf = Math.min(.99, Math.max(.10, conf + (c.number % 3) * 0.02))
  const status: 'pass' | 'wait' | 'low' = conf >= 0.75 ? 'pass' : conf >= 0.5 ? 'wait' : 'low'
  const risk: 'low' | 'mid' | 'high' = conf >= 0.75 ? 'low' : conf >= 0.5 ? 'mid' : 'high'
  return { status, conf, risk }
}

/**
 * Citation-verification domain: server-side decisions merged onto
 * heuristic-scored rows, plus filtering, selection and verify actions.
 */
export function useCitations() {
  const task = useTaskStore()
  const active = ref(0)
  const filterStatus = ref('all')
  const serverCitations = ref<CitationListItem[]>([])
  const serverSummary = ref<Record<string, number>>({})
  const loading = ref(false)

  async function loadCitations() {
    if (!task.current?.id) return
    loading.value = true
    try {
      const resp = await citationApi.list(task.current.id)
      serverCitations.value = resp.items
      serverSummary.value = resp.summary
    } catch (err) {
      ElMessage.error(`加载引用失败:${(err as Error).message}`)
    } finally {
      loading.value = false
    }
  }

  // Map server citation decisions onto the heuristic-derived rows.
  const citations = computed<CiteRow[]>(() => {
    const decisionMap = new Map<number, CitationDecision>()
    for (const c of serverCitations.value) {
      if (c.decision) decisionMap.set(c.number, c.decision)
    }
    const list = task.finalReport?.citations ?? []
    return list.map((c) => {
      const m = classify(c)
      const decision = decisionMap.get(c.number) || null
      let status: 'pass' | 'wait' | 'low' = m.status
      if (decision) {
        if (decision.status === 'pass') status = 'pass'
        else if (decision.status === 'flag') status = 'wait'
        else if (decision.status === 'reject') status = 'low'
      }
      return { n: c.number, body: c.quote || c.title, status, conf: m.conf, risk: m.risk, citation: c, decision }
    })
  })

  const filteredCitations = computed(() => {
    if (filterStatus.value === 'all') return citations.value
    return citations.value.filter((c) => c.status === filterStatus.value)
  })
  const activeCitation = computed<CiteRow | null>(() => filteredCitations.value[active.value] ?? null)

  const passedCount = computed(() => citations.value.filter((c) => c.status === 'pass').length)
  const totalCount = computed(() => citations.value.length)
  const progressPct = computed(() => (totalCount.value ? Math.round(passedCount.value / totalCount.value * 100) : 0))

  // Move the detail panel to the next citation still awaiting review ('wait'),
  // searching forward from the current row and wrapping once.
  function advanceToNextPending() {
    const list = filteredCitations.value
    if (!list.length) return
    const start = active.value
    for (let i = start; i < list.length; i++) {
      if (list[i].status === 'wait') { active.value = i; return }
    }
    for (let i = 0; i < start && i < list.length; i++) {
      if (list[i].status === 'wait') { active.value = i; return }
    }
    ElMessage.success('🎉 没有更多待人工复核的引用')
  }

  // Wired to POST /v1/research/{id}/citations/{n}/verify.
  async function verifyCitation(n: number, status: 'pass' | 'reject' | 'flag' | 'replaced', label: string) {
    if (!task.current?.id) return
    try {
      await citationApi.verify(task.current.id, n, status)
      ElMessage.success(`已${label} [${n}]`)
      await loadCitations()
      // 'flag' leaves the row pending — nothing to advance past.
      if (status !== 'flag') advanceToNextPending()
    } catch (err) {
      ElMessage.error((err as Error).message)
    }
  }

  watch(() => task.current?.id, () => loadCitations())

  return {
    active,
    filterStatus,
    serverCitations,
    serverSummary,
    loading,
    loadCitations,
    citations,
    filteredCitations,
    activeCitation,
    passedCount,
    totalCount,
    progressPct,
    verifyCitation,
    sourceHost,
  }
}
