import { computed, reactive, ref } from 'vue'
import type { Paper, PaperScreeningStatus } from '@/types/research'
import { useProjectStore } from '@/stores/projects'

const PAPER_STATUS_META: Record<PaperScreeningStatus, { label: string; type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = {
  candidate: { label: '候选', type: 'info' },
  included: { label: '纳入', type: 'primary' },
  excluded: { label: '排除', type: 'danger' },
  read: { label: '已读', type: 'success' },
}

export const PAPER_STATUS_OPTIONS: Array<{ label: string; value: PaperScreeningStatus | 'all' }> = [
  { label: '全部', value: 'all' },
  { label: '候选', value: 'candidate' },
  { label: '纳入', value: 'included' },
  { label: '排除', value: 'excluded' },
  { label: '已读', value: 'read' },
]

const PAPER_FORM_DEFAULTS = {
  title: '',
  authorsText: '',
  year: undefined as number | undefined,
  venue: '',
  url: '',
  pdf_url: '',
  code_url: '',
  abstract: '',
  datasetText: '',
  screening_status: 'candidate' as PaperScreeningStatus,
  relevance_score: undefined as number | undefined,
}

const NOTE_FORM_DEFAULTS = {
  problem: '',
  method: '',
  training_setup: '',
  datasetsText: '',
  metricsText: '',
  baselinesText: '',
  main_results: '',
  limitations: '',
  reproducibility_notes: '',
  importantSectionsText: '',
}

export function useProjectLiterature(projectId: () => string) {
  const store = useProjectStore()
  const filter = ref<PaperScreeningStatus | 'all'>('all')
  const query = ref('')
  const searchQuery = ref('')
  const searchLimit = ref(5)
  const searching = ref(false)
  const submitting = ref(false)
  const extracting = ref(false)
  const selectedPaperId = ref<string | null>(null)
  const form = reactive({ ...PAPER_FORM_DEFAULTS })
  const noteForm = reactive({ ...NOTE_FORM_DEFAULTS })

  const papers = computed(() => filterPapers(store.papers, query.value))
  const includedCount = computed(() => countByStatus(store.papers, 'included'))
  const readCount = computed(() => countByStatus(store.papers, 'read'))
  const withCodeCount = computed(() => store.papers.filter((paper) => paper.code_url).length)
  const selectedPaper = computed(() => store.papers.find((paper) => paper.id === selectedPaperId.value) || null)
  const selectedNotes = computed(() => selectedPaperId.value ? (store.paperNotes[selectedPaperId.value] || []) : [])

  async function load() {
    await Promise.all([store.loadProject(projectId()), loadPapers()])
  }

  async function loadPapers() {
    await store.loadPapers(projectId(), { screening_status: filter.value })
    await selectDefaultPaper()
  }

  async function selectDefaultPaper() {
    const currentStillVisible = store.papers.some((paper) => paper.id === selectedPaperId.value)
    if (currentStillVisible || !store.papers.length) return
    await selectPaper(store.papers[0])
  }

  async function createPaper() {
    await store.createPaper(projectId(), {
      title: form.title.trim(),
      authors: splitList(form.authorsText),
      year: form.year || null,
      venue: emptyToNull(form.venue),
      abstract: emptyToNull(form.abstract),
      url: emptyToNull(form.url),
      pdf_url: emptyToNull(form.pdf_url),
      code_url: emptyToNull(form.code_url),
      dataset_mentions: splitList(form.datasetText),
      screening_status: form.screening_status,
      relevance_score: form.relevance_score ?? null,
    })
    resetPaperForm()
    await loadPapers()
  }

  async function runPaperSearch() {
    const result = await store.searchPapers(projectId(), searchQuery.value.trim(), searchLimit.value)
    await selectDefaultPaper()
    return {
      created: Number(result.structured_output.created_count || 0),
      skipped: Number(result.structured_output.skipped_duplicates || 0),
    }
  }

  async function selectPaper(paper: Paper) {
    selectedPaperId.value = paper.id
    await store.loadPaperNotes(projectId(), paper.id)
  }

  async function createNote() {
    const paper = selectedPaper.value
    if (!paper) throw new Error('no selected paper')
    await store.createPaperNote(projectId(), paper.id, {
      problem: emptyToNull(noteForm.problem),
      method: emptyToNull(noteForm.method),
      training_setup: emptyToNull(noteForm.training_setup),
      datasets: splitList(noteForm.datasetsText),
      metrics: splitList(noteForm.metricsText),
      baselines: splitList(noteForm.baselinesText),
      main_results: emptyToNull(noteForm.main_results),
      limitations: emptyToNull(noteForm.limitations),
      reproducibility_notes: emptyToNull(noteForm.reproducibility_notes),
      important_sections: splitList(noteForm.importantSectionsText),
    })
    resetNoteForm()
  }

  async function extractNote() {
    const paper = selectedPaper.value
    if (!paper) throw new Error('no selected paper')
    const { source } = await store.extractPaperNote(projectId(), paper.id)
    return { source }
  }

  function resetPaperForm() {
    Object.assign(form, PAPER_FORM_DEFAULTS)
  }

  function resetNoteForm() {
    Object.assign(noteForm, NOTE_FORM_DEFAULTS)
  }

  return {
    store,
    filter,
    query,
    searchQuery,
    searchLimit,
    searching,
    submitting,
    extracting,
    selectedPaperId,
    form,
    noteForm,
    papers,
    includedCount,
    readCount,
    withCodeCount,
    selectedPaper,
    selectedNotes,
    load,
    loadPapers,
    createPaper,
    runPaperSearch,
    selectPaper,
    createNote,
    extractNote,
  }
}

export function splitList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function emptyToNull(value: string) {
  const trimmed = value.trim()
  return trimmed || null
}

export function paperStatusMeta(status: PaperScreeningStatus) {
  return PAPER_STATUS_META[status]
}

export function formatPaperMeta(paper: Paper) {
  return [paper.year || '', paper.venue || '', paper.authors.slice(0, 3).join(', ')]
    .filter(Boolean)
    .join(' · ') || '—'
}

export function formatScore(value?: number | null) {
  return value === null || value === undefined ? '—' : value.toFixed(2)
}

function filterPapers(papers: Paper[], rawQuery: string) {
  const q = rawQuery.trim().toLowerCase()
  if (!q) return papers
  return papers.filter((paper) =>
    [
      paper.title,
      paper.abstract || '',
      paper.venue || '',
      paper.authors.join(' '),
      paper.dataset_mentions.join(' '),
    ].join('\n').toLowerCase().includes(q),
  )
}

function countByStatus(papers: Paper[], status: PaperScreeningStatus) {
  return papers.filter((paper) => paper.screening_status === status).length
}
