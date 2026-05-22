import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { projectApi } from '@/api/client'
import { PaperNote as PaperNoteSchema } from '@/types/research'
import type {
  CreatePaperInput,
  CreatePaperNoteInput,
  CreateResearchProjectInput,
  Paper,
  PaperNote,
  PaperScreeningStatus,
  ResearchProject,
  ToolTraceItem,
} from '@/types/research'

export const useProjectStore = defineStore('projects', () => {
  const projects = ref<ResearchProject[]>([])
  const current = ref<ResearchProject | null>(null)
  const papers = ref<Paper[]>([])
  const paperNotes = ref<Record<string, PaperNote[]>>({})
  const trace = ref<ToolTraceItem[]>([])
  const loading = ref(false)
  const papersLoading = ref(false)
  const notesLoading = ref(false)
  const traceLoading = ref(false)
  const error = ref<string | null>(null)

  const total = computed(() => projects.value.length)
  const activeCount = computed(() =>
    projects.value.filter((project) => ['planning', 'running', 'waiting_review'].includes(project.status)).length,
  )

  async function loadProjects(limit = 50) {
    loading.value = true
    error.value = null
    try {
      projects.value = await projectApi.list(limit)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
  }

  async function createProject(input: CreateResearchProjectInput) {
    loading.value = true
    error.value = null
    try {
      const project = await projectApi.create(input)
      projects.value = [project, ...projects.value.filter((item) => item.id !== project.id)]
      current.value = project
      return project
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadProject(projectId: string) {
    loading.value = true
    error.value = null
    try {
      current.value = await projectApi.get(projectId)
      return current.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      current.value = null
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadTrace(projectId: string) {
    traceLoading.value = true
    error.value = null
    try {
      trace.value = await projectApi.trace(projectId)
      return trace.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      trace.value = []
      throw err
    } finally {
      traceLoading.value = false
    }
  }

  async function loadPapers(
    projectId: string,
    params: { limit?: number; screening_status?: PaperScreeningStatus | 'all' } = {},
  ) {
    papersLoading.value = true
    error.value = null
    try {
      const { screening_status, ...rest } = params
      papers.value = await projectApi.listPapers(projectId, {
        ...rest,
        ...(screening_status && screening_status !== 'all' ? { screening_status } : {}),
      })
      return papers.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      papers.value = []
      throw err
    } finally {
      papersLoading.value = false
    }
  }

  async function createPaper(projectId: string, input: CreatePaperInput) {
    papersLoading.value = true
    error.value = null
    try {
      const paper = await projectApi.createPaper(projectId, input)
      papers.value = [paper, ...papers.value.filter((item) => item.id !== paper.id)]
      return paper
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      papersLoading.value = false
    }
  }

  async function loadPaperNotes(projectId: string, paperId: string) {
    notesLoading.value = true
    error.value = null
    try {
      paperNotes.value = {
        ...paperNotes.value,
        [paperId]: await projectApi.listPaperNotes(projectId, paperId),
      }
      return paperNotes.value[paperId]
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      paperNotes.value = { ...paperNotes.value, [paperId]: [] }
      throw err
    } finally {
      notesLoading.value = false
    }
  }

  async function createPaperNote(projectId: string, paperId: string, input: CreatePaperNoteInput) {
    notesLoading.value = true
    error.value = null
    try {
      const note = await projectApi.createPaperNote(projectId, paperId, input)
      upsertPaperNote(paperId, note)
      return note
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      notesLoading.value = false
    }
  }

  async function extractPaperNote(projectId: string, paperId: string) {
    notesLoading.value = true
    error.value = null
    try {
      const result = await projectApi.extractPaperNote(projectId, paperId)
      const note = PaperNoteSchema.parse(result.structured_output.note)
      upsertPaperNote(paperId, note)
      trace.value = await projectApi.trace(projectId)
      return {
        result,
        note,
        source: String(result.structured_output.extraction_source || ''),
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      notesLoading.value = false
    }
  }

  async function searchPapers(projectId: string, query: string, limit = 5) {
    papersLoading.value = true
    error.value = null
    try {
      const result = await projectApi.searchPapers(projectId, { query, limit })
      papers.value = await projectApi.listPapers(projectId)
      trace.value = await projectApi.trace(projectId)
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      papersLoading.value = false
    }
  }

  function clearCurrent() {
    current.value = null
    papers.value = []
    paperNotes.value = {}
    trace.value = []
  }

  function upsertPaperNote(paperId: string, note: PaperNote) {
    const existing = paperNotes.value[paperId] || []
    paperNotes.value = {
      ...paperNotes.value,
      [paperId]: [note, ...existing.filter((item) => item.id !== note.id)],
    }
  }

  return {
    projects,
    current,
    papers,
    paperNotes,
    trace,
    loading,
    papersLoading,
    notesLoading,
    traceLoading,
    error,
    total,
    activeCount,
    loadProjects,
    createProject,
    loadProject,
    loadPapers,
    createPaper,
    loadPaperNotes,
    createPaperNote,
    extractPaperNote,
    searchPapers,
    loadTrace,
    clearCurrent,
  }
})
