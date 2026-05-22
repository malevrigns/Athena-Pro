import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi, type KnowledgeCollection, type KnowledgeItem, type KnowledgeOverview } from '@/api/client'

/**
 * Knowledge-base data layer: server collections / items / overview / tags,
 * the filter + pagination state that drives them, and display-shaped views.
 * Mutations (create / upload / verify / delete) stay in the view and call the
 * loaders returned here to refresh.
 */
export function useKnowledgeItems() {
  // Filter + pagination state
  const search = ref('')
  const status = ref('all')
  const tagFilter = ref('all')
  const collectionFilter = ref('')
  const pageSize = ref('10')
  const page = ref(1)

  // Server data
  const apiCollections = ref<KnowledgeCollection[]>([])
  const apiItems = ref<KnowledgeItem[]>([])
  const apiTotal = ref(0)
  const apiOverview = ref<KnowledgeOverview | null>(null)
  const apiTags = ref<{ label: string; count: number }[]>([])
  const loading = ref(false)

  async function loadCollections() {
    apiCollections.value = (await knowledgeApi.collections()).items
  }
  async function loadOverview() {
    apiOverview.value = await knowledgeApi.overview()
  }
  async function loadTags() {
    apiTags.value = (await knowledgeApi.tags(10)).items
  }
  async function loadItems() {
    loading.value = true
    try {
      const limit = Number(pageSize.value)
      const resp = await knowledgeApi.items({
        collection_id: collectionFilter.value || undefined,
        search: search.value || tagFilter.value !== 'all' ? (search.value || tagFilter.value) : undefined,
        status: status.value !== 'all' ? status.value : undefined,
        limit,
        offset: (page.value - 1) * limit,
      })
      apiItems.value = resp.items
      apiTotal.value = resp.total
    } finally {
      loading.value = false
    }
  }
  async function loadAll() {
    await loadCollections()
    await loadOverview()
    await loadTags()
    await loadItems()
  }

  const effectiveCollections = computed(() => apiCollections.value.map((c) => ({
    id: c.id, name: c.name, icon: null, color: c.color || 'blue',
    count: '—', updated: c.updated_at ? new Date(c.updated_at).toLocaleString('zh-CN') : '—',
    desc: c.description || '',
  })))

  const effectiveItems = computed(() => apiItems.value.map((it) => ({
    id: it.id, name: it.name, sub: it.summary || '',
    type: it.type || '—', source: it.source || '—',
    tags: it.tags, time: it.updated_at ? new Date(it.updated_at).toLocaleString('zh-CN') : '—',
    usage: it.usage_count, status: it.status,
  })))

  const effectiveOverview = computed(() => (apiOverview.value ? [
    { icon: '🗄', color: 'blue',   value: String(apiOverview.value.total_items),    label: '知识总量' },
    { icon: '✓',  color: 'green',  value: String(apiOverview.value.verified_items), label: '已验证条目' },
    { icon: '#',  color: 'purple', value: String(apiOverview.value.active_tags),    label: '活跃标签' },
    { icon: '%',  color: 'orange', value: apiOverview.value.verified_pct.toFixed(1) + '%', label: '验证率' },
  ] : []))

  const totalPages = computed(() => Math.max(1, Math.ceil(apiTotal.value / Math.max(1, Number(pageSize.value)))))

  function clearFilters() {
    const alreadyClear = !search.value && status.value === 'all' && tagFilter.value === 'all' && !collectionFilter.value
    search.value = ''
    status.value = 'all'
    tagFilter.value = 'all'
    collectionFilter.value = ''
    page.value = 1
    ElMessage.info(alreadyClear ? '当前没有筛选条件' : '已清除筛选')
  }

  // Any filter change resets to page 1; page changes just reload.
  watch([search, status, pageSize, collectionFilter, tagFilter], () => {
    page.value = 1
    loadItems()
  })
  watch(page, () => loadItems())

  return {
    search,
    status,
    tagFilter,
    collectionFilter,
    pageSize,
    page,
    apiCollections,
    apiItems,
    apiTotal,
    apiOverview,
    apiTags,
    loading,
    loadCollections,
    loadOverview,
    loadTags,
    loadItems,
    loadAll,
    effectiveCollections,
    effectiveItems,
    effectiveOverview,
    totalPages,
    clearFilters,
  }
}
