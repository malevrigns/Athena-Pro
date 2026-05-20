<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeApi, type KnowledgeCollection, type KnowledgeItem, type KnowledgeOverview } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.coll-card')
useEntrance('.ii-row, .grid-item', { delay: (_el, i) => 80 + i * 40 })
useEntrance('.kpi-card, .recent-list li, .tag-chip', { delay: (_el, i) => 120 + i * 50 })
import {
  Search, Upload, Plus, FolderOpened, Refresh,
  Document, OfficeBuilding, Reading, Notebook,
  Files, Box, MoreFilled, Grid, List, Delete, CircleCheck,
} from '@element-plus/icons-vue'

const session = useSessionStore()

// Filter state
const search = ref('')
const status = ref('all')
const tagFilter = ref('all')
const collectionFilter = ref('')
const viewMode = ref<'list' | 'grid'>('list')
const pageSize = ref('10')
const page = ref(1)

// API data
const apiCollections = ref<KnowledgeCollection[]>([])
const apiItems = ref<KnowledgeItem[]>([])
const apiTotal = ref(0)
const apiOverview = ref<KnowledgeOverview | null>(null)
const apiTags = ref<{ label: string; count: number }[]>([])
const loading = ref(false)

async function loadCollections() { apiCollections.value = (await knowledgeApi.collections()).items }
async function loadOverview() { apiOverview.value = await knowledgeApi.overview() }
async function loadTags() { apiTags.value = (await knowledgeApi.tags(10)).items }

async function loadItems() {
  loading.value = true
  try {
    const limit = Number(pageSize.value)
    const resp = await knowledgeApi.items({
      collection_id: collectionFilter.value || undefined,
      search: (search.value || tagFilter.value !== 'all' ? (search.value || tagFilter.value) : undefined),
      status: status.value !== 'all' ? status.value : undefined,
      limit,
      offset: (page.value - 1) * limit,
    })
    apiItems.value = resp.items
    apiTotal.value = resp.total
  } finally { loading.value = false }
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

const effectiveOverview = computed(() => apiOverview.value ? [
  { icon: '🗄', color: 'blue',   value: String(apiOverview.value.total_items),    label: '知识总量' },
  { icon: '✓',  color: 'green',  value: String(apiOverview.value.verified_items), label: '已验证条目' },
  { icon: '#',  color: 'purple', value: String(apiOverview.value.active_tags),    label: '活跃标签' },
  { icon: '%',  color: 'orange', value: apiOverview.value.verified_pct.toFixed(1) + '%', label: '验证率' },
] : [])

const totalPages = computed(() => Math.max(1, Math.ceil(apiTotal.value / Math.max(1, Number(pageSize.value)))))

onMounted(async () => {
  await loadCollections()
  await loadOverview()
  await loadTags()
  await loadItems()
})
watch([search, status, pageSize, collectionFilter, tagFilter], () => { page.value = 1; loadItems() })
watch(page, () => loadItems())

// ---------- Filter actions ----------
function clearFilters() {
  search.value = ''
  status.value = 'all'
  tagFilter.value = 'all'
  collectionFilter.value = ''
  page.value = 1
}

function pickCollection(id: string) {
  collectionFilter.value = collectionFilter.value === id ? '' : id
}

function pickTag(label: string) {
  search.value = label
  ElMessage.info(`按标签筛选:${label}`)
}

// ---------- Create collection dialog ----------
const collDialog = ref(false)
const collForm = ref<{ name: string; description: string; color: string }>({ name: '', description: '', color: 'blue' })
async function submitCollection() {
  if (!collForm.value.name.trim()) { ElMessage.warning('请输入集合名称'); return }
  try {
    await knowledgeApi.createCollection(collForm.value)
    ElMessage.success('集合已创建')
    collDialog.value = false
    collForm.value = { name: '', description: '', color: 'blue' }
    await loadCollections(); await loadOverview()
  } catch (e) { ElMessage.error((e as Error).message) }
}

// ---------- Import knowledge (manual entry) dialog ----------
const itemDialog = ref(false)
const itemForm = ref<{ name: string; summary: string; type: string; source: string; tags: string; collection_id: string }>(
  { name: '', summary: '', type: '', source: '', tags: '', collection_id: '' },
)
async function submitItem() {
  if (!itemForm.value.name.trim()) { ElMessage.warning('请输入条目名称'); return }
  try {
    await knowledgeApi.createItem({
      name: itemForm.value.name,
      summary: itemForm.value.summary,
      type: itemForm.value.type || undefined,
      source: itemForm.value.source || undefined,
      tags: itemForm.value.tags.split(/[,, ]+/).map((s) => s.trim()).filter(Boolean),
      collection_id: itemForm.value.collection_id || undefined,
    })
    ElMessage.success('条目已添加')
    itemDialog.value = false
    itemForm.value = { name: '', summary: '', type: '', source: '', tags: '', collection_id: '' }
    await loadItems(); await loadOverview(); await loadTags()
  } catch (e) { ElMessage.error((e as Error).message) }
}

// ---------- File upload ----------
const uploadDialog = ref(false)
const uploadCollection = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
function openUploadDialog() { uploadDialog.value = true }
function pickFile() { fileInput.value?.click() }
async function onFileChange(ev: Event) {
  const target = ev.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  try {
    const resp = await knowledgeApi.uploadDocument(file, uploadCollection.value || undefined)
    ElMessage.success(`已上传 ${resp.filename}`)
    uploadDialog.value = false
    target.value = ''
    await loadItems(); await loadOverview()
  } catch (e) { ElMessage.error((e as Error).message) }
}

// ---------- Item actions ----------
async function verifyItem(id: string) {
  try {
    await knowledgeApi.verifyItem(id)
    ElMessage.success('已标记为已验证')
    await loadItems(); await loadOverview()
  } catch (e) { ElMessage.error((e as Error).message) }
}

async function deleteItem(id: string, name: string) {
  try {
    await ElMessageBox.confirm(`确定删除「${name}」?`, '删除条目', { type: 'warning' })
    await knowledgeApi.deleteItem(id)
    ElMessage.success('已删除')
    await loadItems(); await loadOverview()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

// ---------- Export CSV ----------
async function exportCsv() {
  await knowledgeApi.downloadCsv({
    collection_id: collectionFilter.value || undefined,
    search: search.value || undefined,
    status: status.value !== 'all' ? status.value : undefined,
  })
}

const collections = [
  { id: 'industry',  name: '行业报告库', icon: Document,       color: 'blue',   count: '1,287', updated: '2 小时前', desc: '覆盖全球主要行业的研究报告与市场洞察' },
  { id: 'company',   name: '公司与财报库', icon: OfficeBuilding, color: 'green',  count: '2,356', updated: '1 小时前', desc: '上市公司资料、财报、公告与分析' },
  { id: 'policy',    name: '政策法规库',   icon: Reading,        color: 'purple', count: '892',   updated: '5 小时前', desc: '国内外政策法规、标准与监管文件' },
  { id: 'paper',     name: '技术论文库',   icon: Notebook,       color: 'orange', count: '3,142', updated: '3 小时前', desc: '学术论文、预印本与技术白皮书' },
  { id: 'template',  name: '研究模板库',   icon: Files,          color: 'pink',   count: '158',   updated: '1 天前',   desc: '研究方法、分析框架与报告模板' },
  { id: 'history',   name: '历史项目沉淀', icon: Box,            color: 'cyan',   count: '976',   updated: '2 小时前', desc: '历史项目中的结构化知识与结论沉淀' },
]

const items = [
  { name: '2026 AI Agent 行业报告摘要', sub: 'IDC 2026 年全球 AI Agent 市场预测与…', type: '行业报告', source: 'IDC',        tags: ['AI Agent','市场预测'], time: '2025-05-08 10:32', usage: 128, status: 'verified' },
  { name: '新能源车产业链公司库',         sub: '包含 1200+ 上市公司及产业链关键…', type: '公司数据库', source: '公开数据',     tags: ['新能源','汽车'],   time: '2025-05-08 09:15', usage: 96,  status: 'verified' },
  { name: '医药研发术语词典',             sub: '药物研发全流程术语与定义 (中英对照)', type: '词典',     source: '内部整理',     tags: ['医疗','术语'],     time: '2025-05-07 18:44', usage: 64,  status: 'verified' },
  { name: 'RAG 最佳实践模板',             sub: 'RAG 系统搭建与优化实践模板',        type: '研究模板', source: '内部整理',     tags: ['RAG','大模型'],   time: '2025-05-07 16:21', usage: 52,  status: 'pending'  },
  { name: '跨境电商行业数据集',           sub: '2019-2024 交易现状与用户行为数据', type: '数据集',   source: '第三方数据',   tags: ['电商','跨境'],     time: '2025-05-07 11:09', usage: 38,  status: 'verified' },
]

const overview = [
  { icon: '🗄', color: 'blue',   value: '8,811', label: '知识总量', sub: '较上周 +312' },
  { icon: '✓',  color: 'green',  value: '7,434', label: '已验证条目', sub: '占比 84.4%' },
  { icon: '+',  color: 'purple', value: '142',   label: '本周新增', sub: '较上周 +28' },
  { icon: '🔥', color: 'orange', value: '1,256', label: '活跃标签', sub: '较上周 +96' },
]

const hotTags = [
  { label: 'AI Agent',  count: '1,234' },
  { label: '新能源',    count: '986' },
  { label: '医疗',      count: '872' },
  { label: '金融',      count: '764' },
  { label: 'RAG',       count: '612' },
]

const recentUpdates = [
  { title: '2026 AI Agent 行业报告摘要',  desc: '更新了标签:市场预测,AI Agent',  ago: '2 小时前' },
  { title: '新能源车产业链公司库',         desc: '新增 48 家公司数据',             ago: '3 小时前' },
  { title: '医药研发术语词典',             desc: '更新了 32 个术语定义',           ago: '5 小时前' },
  { title: 'RAG 最佳实践模板',             desc: '更新了模板内容 v2.1',           ago: '1 天前' },
  { title: '跨境电商行业数据集',           desc: '新增 2024 年 Q1 数据',          ago: '1 天前' },
]
</script>

<template>
  <div class="kb">
    <div class="kb-grid">
      <div class="kb-main">
        <ElAlert v-if="!apiItems.length && !apiOverview?.total_items" type="info" :closable="false" show-icon class="demo-banner">
          <template #title>知识库为空</template>
          <span>使用「上传文档」或 POST /v1/knowledge/items 即可向库内填充条目。底部集合卡片为默认种子集合,可直接归属。</span>
        </ElAlert>
        <!-- Search row -->
        <section class="kb-search-row">
          <ElInput v-model="search" placeholder="搜索知识条目、数据集、研究模板或标签" :prefix-icon="Search" size="large" class="kb-search" />
          <button class="primary-btn lg" @click="itemDialog = true"><ElIcon><FolderOpened /></ElIcon><span>导入知识</span></button>
          <button class="btn-secondary" @click="collDialog = true"><ElIcon><Plus /></ElIcon><span>创建集合</span></button>
          <button class="btn-secondary" @click="openUploadDialog"><ElIcon><Upload /></ElIcon><span>上传文档</span></button>
        </section>

        <!-- Filter -->
        <section class="kb-filters card">
          <div class="filter-field">
            <span class="filter-label">集合</span>
            <ElSelect v-model="collectionFilter" size="default" style="width: 160px;" clearable>
              <ElOption label="全部集合" value="" />
              <ElOption v-for="c in apiCollections" :key="c.id" :label="c.name" :value="c.id" />
            </ElSelect>
          </div>
          <div class="filter-field">
            <span class="filter-label">状态</span>
            <ElSelect v-model="status" size="default" style="width: 130px;">
              <ElOption label="全部" value="all" />
              <ElOption label="已验证" value="verified" />
              <ElOption label="待验证" value="pending" />
            </ElSelect>
          </div>
          <div class="filter-field">
            <span class="filter-label">标签</span>
            <ElSelect v-model="tagFilter" size="default" style="width: 160px;">
              <ElOption label="全部标签" value="all" />
              <ElOption v-for="t in apiTags" :key="t.label" :label="t.label" :value="t.label" />
            </ElSelect>
          </div>
          <button class="btn-secondary" @click="clearFilters"><ElIcon><Refresh /></ElIcon><span>清除筛选</span></button>
        </section>

        <!-- Collections -->
        <section class="kb-block">
          <header class="block-head"><h3>知识集合</h3></header>
          <div class="coll-grid">
            <article
              v-for="c in (effectiveCollections.length ? effectiveCollections : collections)" :key="c.id"
              class="coll-card" :class="{ 'is-active': collectionFilter === c.id }"
              @click="pickCollection(c.id)"
            >
              <div class="coll-ico" :data-color="c.color">
                <ElIcon v-if="(c as any).icon && typeof (c as any).icon !== 'string'"><component :is="(c as any).icon" /></ElIcon>
                <span v-else>📚</span>
              </div>
              <h4>{{ c.name }}</h4>
              <div class="coll-count">{{ (c as any).count || '—' }} 条目</div>
              <div class="coll-time">更新:{{ (c as any).updated || '—' }}</div>
              <p>{{ (c as any).desc || '' }}</p>
            </article>
          </div>
        </section>

        <!-- Items -->
        <section class="card kb-items">
          <header class="items-head">
            <h3>知识条目</h3>
            <div class="items-actions">
              <div class="view-toggle">
                <button :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图"><ElIcon><List /></ElIcon></button>
                <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="网格视图"><ElIcon><Grid /></ElIcon></button>
              </div>
              <button class="btn-secondary" @click="exportCsv"><ElIcon><Upload /></ElIcon><span>导出 CSV</span></button>
            </div>
          </header>

          <ElEmpty v-if="!effectiveItems.length" :image-size="80" description="没有条目。使用「导入知识」或「上传文档」开始填充。" />

          <!-- List view -->
          <div v-else-if="viewMode === 'list'" class="items-table">
            <div class="ih-row">
              <div>条目名称</div>
              <div>类型</div>
              <div>来源</div>
              <div>标签</div>
              <div>更新时间</div>
              <div>使用次数</div>
              <div>状态</div>
              <div>操作</div>
            </div>
            <div v-for="(it, i) in effectiveItems" :key="it.id" class="ii-row">
              <div class="ii-name">
                <div class="ii-ico" :data-color="['blue','green','orange','pink','cyan'][i % 5]">📄</div>
                <div>
                  <div class="ii-title" :title="it.name">{{ it.name }}</div>
                  <div class="ii-sub">{{ it.sub }}</div>
                </div>
              </div>
              <div class="ii-type">{{ it.type }}</div>
              <div class="ii-source">{{ it.source }}</div>
              <div class="ii-tags">
                <span v-for="t in it.tags.slice(0, 3)" :key="t" class="tag tag-blue">{{ t }}</span>
                <span v-if="it.tags.length > 3" class="tag tag-more">+{{ it.tags.length - 3 }}</span>
              </div>
              <div class="ii-time">{{ it.time }}</div>
              <div class="ii-usage">{{ it.usage }}</div>
              <div>
                <span class="tag" :class="it.status === 'verified' ? 'tag-green' : 'tag-yellow'">
                  <i /> {{ it.status === 'verified' ? '已验证' : '待验证' }}
                </span>
              </div>
              <div class="ii-actions">
                <ElDropdown trigger="click">
                  <button class="td-ico-btn"><ElIcon><MoreFilled /></ElIcon></button>
                  <template #dropdown>
                    <ElDropdownMenu>
                      <ElDropdownItem :disabled="it.status === 'verified'" @click="verifyItem(it.id)">
                        <ElIcon><CircleCheck /></ElIcon> 标记已验证
                      </ElDropdownItem>
                      <ElDropdownItem divided @click="deleteItem(it.id, it.name)">
                        <ElIcon><Delete /></ElIcon> 删除
                      </ElDropdownItem>
                    </ElDropdownMenu>
                  </template>
                </ElDropdown>
              </div>
            </div>
          </div>

          <!-- Grid view -->
          <div v-else class="items-grid">
            <article v-for="(it, i) in effectiveItems" :key="it.id" class="grid-item">
              <div class="ii-ico" :data-color="['blue','green','orange','pink','cyan'][i % 5]">📄</div>
              <h4 :title="it.name">{{ it.name }}</h4>
              <p>{{ it.sub }}</p>
              <div class="grid-meta">
                <span class="tag" :class="it.status === 'verified' ? 'tag-green' : 'tag-yellow'">{{ it.status === 'verified' ? '已验证' : '待验证' }}</span>
                <span class="ii-time">{{ it.time }}</span>
              </div>
              <div class="grid-tags">
                <span v-for="t in it.tags.slice(0, 4)" :key="t" class="tag tag-blue">{{ t }}</span>
              </div>
              <div class="grid-actions">
                <button class="td-ico-btn" :disabled="it.status === 'verified'" @click="verifyItem(it.id)" title="标记已验证">
                  <ElIcon><CircleCheck /></ElIcon>
                </button>
                <button class="td-ico-btn" @click="deleteItem(it.id, it.name)" title="删除">
                  <ElIcon><Delete /></ElIcon>
                </button>
              </div>
            </article>
          </div>

          <div v-if="apiTotal > 0" class="hist-pager">
            <span class="pager-count">共 {{ apiTotal }} 条</span>
            <div class="pager-mid">
              <ElSelect v-model="pageSize" size="default" style="width: 90px;">
                <ElOption label="10 条/页" value="10" />
                <ElOption label="20 条/页" value="20" />
                <ElOption label="50 条/页" value="50" />
              </ElSelect>
              <button :disabled="page <= 1" @click="page = Math.max(1, page - 1)">‹</button>
              <button class="active">{{ page }}</button>
              <span>/ {{ totalPages }}</span>
              <button :disabled="page >= totalPages" @click="page = Math.min(totalPages, page + 1)">›</button>
            </div>
          </div>
        </section>
      </div>

      <div class="kb-side">
        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">知识总览</h3>
            <a class="link-mini"><ElIcon><Refresh /></ElIcon> 刷新</a>
          </header>
          <div class="kpi-grid">
            <div v-for="(o, i) in (effectiveOverview.length ? effectiveOverview : overview)" :key="i" class="kpi-card">
              <div class="kpi-ico" :data-color="o.color">{{ o.icon }}</div>
              <div class="kpi-value">{{ o.value }}</div>
              <div class="kpi-label">{{ o.label }}</div>
              <div v-if="(o as any).sub" class="kpi-sub">{{ (o as any).sub }}</div>
            </div>
          </div>
        </article>

        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">热门标签</h3>
            <a class="link-mini">更多 ›</a>
          </header>
          <div class="tag-cloud">
            <ElEmpty v-if="!apiTags.length" :image-size="40" description="暂无标签" />
            <button v-for="t in apiTags" :key="t.label" class="tag-chip" @click="pickTag(t.label)">
              <span>{{ t.label }}</span>
              <small>{{ t.count }}</small>
            </button>
          </div>
        </article>

        <article class="card card-pad">
          <header class="section-head">
            <h3 class="card-title">最近更新</h3>
            <a class="link-mini">更多 ›</a>
          </header>
          <ElEmpty v-if="!apiItems.length" :image-size="40" description="暂无更新" />
          <ul v-else class="recent-list">
            <li v-for="it in apiItems.slice(0, 5)" :key="it.id">
              <div class="ru-title">{{ it.name }}</div>
              <div class="ru-desc">{{ it.summary || '(无摘要)' }}</div>
              <div class="ru-time">{{ new Date(it.updated_at).toLocaleString('zh-CN') }}</div>
            </li>
          </ul>
        </article>
      </div>
    </div>

    <!-- Create collection dialog -->
    <ElDialog v-model="collDialog" title="创建集合" width="460px">
      <ElForm label-position="top">
        <ElFormItem label="名称" required>
          <ElInput v-model="collForm.name" placeholder="例如:行业研究·消费电子" maxlength="60" show-word-limit />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="collForm.description" type="textarea" :rows="2" placeholder="简单描述集合用途" maxlength="200" show-word-limit />
        </ElFormItem>
        <ElFormItem label="颜色">
          <ElSelect v-model="collForm.color" style="width: 100%;">
            <ElOption v-for="c in ['blue','green','purple','orange','pink','cyan']" :key="c" :label="c" :value="c" />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="collDialog = false">取消</ElButton>
        <ElButton type="primary" @click="submitCollection">创建</ElButton>
      </template>
    </ElDialog>

    <!-- Create item dialog -->
    <ElDialog v-model="itemDialog" title="导入知识条目" width="560px">
      <ElForm label-position="top">
        <ElFormItem label="名称" required>
          <ElInput v-model="itemForm.name" placeholder="条目名称" maxlength="120" show-word-limit />
        </ElFormItem>
        <ElFormItem label="所属集合">
          <ElSelect v-model="itemForm.collection_id" clearable style="width: 100%;">
            <ElOption label="(不归属)" value="" />
            <ElOption v-for="c in apiCollections" :key="c.id" :label="c.name" :value="c.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="摘要">
          <ElInput v-model="itemForm.summary" type="textarea" :rows="3" placeholder="简短摘要" maxlength="500" show-word-limit />
        </ElFormItem>
        <ElFormItem label="类型 / 来源">
          <div style="display: flex; gap: 8px;">
            <ElInput v-model="itemForm.type"   placeholder="类型,如 报告/数据集" />
            <ElInput v-model="itemForm.source" placeholder="来源,如 IDC" />
          </div>
        </ElFormItem>
        <ElFormItem label="标签 (逗号分隔)">
          <ElInput v-model="itemForm.tags" placeholder="AI Agent, 市场预测" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="itemDialog = false">取消</ElButton>
        <ElButton type="primary" @click="submitItem">创建</ElButton>
      </template>
    </ElDialog>

    <!-- Upload dialog -->
    <ElDialog v-model="uploadDialog" title="上传文档" width="460px">
      <ElForm label-position="top">
        <ElFormItem label="所属集合">
          <ElSelect v-model="uploadCollection" clearable style="width: 100%;">
            <ElOption label="(不归属)" value="" />
            <ElOption v-for="c in apiCollections" :key="c.id" :label="c.name" :value="c.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="文件">
          <div class="upload-zone" @click="pickFile">
            <ElIcon :size="28" color="var(--primary)"><Upload /></ElIcon>
            <p>点击选择文件 (任意类型)</p>
            <small>文件将存放在服务端 ATHENA_DATA_DIR/knowledge/ 下,首 1KB 内容作为摘要</small>
            <input ref="fileInput" type="file" style="display:none;" @change="onFileChange" />
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="uploadDialog = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.kb-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}
.kb-main, .kb-side { display: grid; gap: 16px; min-width: 0; }
.demo-banner { border-radius: 8px; }

.coll-card.is-active {
  border-color: var(--primary) !important;
  background: var(--primary-soft) !important;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, .15) !important;
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  padding: 14px 18px;
}
.grid-item {
  position: relative;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  display: grid; gap: 6px;
  transition: all .15s ease;
}
.grid-item:hover { border-color: var(--primary-line); box-shadow: var(--shadow-2); }
.grid-item h4 {
  margin: 4px 0 0; font-size: 13.5px; font-weight: 600; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.grid-item p {
  margin: 0; font-size: 12px; color: var(--muted); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.grid-meta { display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; color: var(--muted); }
.grid-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.grid-actions { display: flex; gap: 4px; justify-content: flex-end; }

.upload-zone {
  border: 2px dashed var(--border-strong);
  border-radius: 10px;
  padding: 28px 14px;
  text-align: center;
  cursor: pointer;
  transition: all .15s ease;
}
.upload-zone:hover { border-color: var(--primary); background: var(--primary-soft); }
.upload-zone p { margin: 8px 0 4px; font-size: 13.5px; font-weight: 500; color: var(--text); }
.upload-zone small { color: var(--muted); font-size: 11.5px; }

.pager-mid button:disabled { opacity: .4; cursor: not-allowed; }
.pager-mid span:not(.dot) { color: var(--muted); font-size: 12px; padding: 0 6px; }
.td-ico-btn:disabled { opacity: .4; cursor: not-allowed; }


.kb-search-row { display: flex; gap: 10px; align-items: center; }
.kb-search { flex: 1; }
.kb-search :deep(.el-input__wrapper) { height: 44px; padding: 0 14px; border-radius: 10px; }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 38px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .12s ease;
}
.btn-secondary:hover { border-color: var(--primary-line); color: var(--primary); }

.kb-filters {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 18px;
  flex-wrap: wrap;
}
.filter-field { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 12.5px; color: var(--muted); }

.kb-block { display: grid; gap: 12px; }
.block-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }

.coll-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.coll-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  display: grid; gap: 4px;
  cursor: pointer;
  transition: all .15s ease;
}
.coll-card:hover { border-color: var(--primary-line); box-shadow: var(--shadow-2); }
.coll-ico {
  width: 36px; height: 36px;
  border-radius: 8px;
  display: grid; place-items: center;
  margin-bottom: 6px;
}
.coll-ico[data-color='blue']   { background: #dbeafe; color: #2563eb; }
.coll-ico[data-color='green']  { background: #dcfce7; color: #16a34a; }
.coll-ico[data-color='purple'] { background: #ede9fe; color: #7c3aed; }
.coll-ico[data-color='orange'] { background: #ffedd5; color: #f97316; }
.coll-ico[data-color='pink']   { background: #fce7f3; color: #db2777; }
.coll-ico[data-color='cyan']   { background: #cffafe; color: #0891b2; }
.coll-card h4 { margin: 0; font-size: 13.5px; font-weight: 600; color: var(--text); }
.coll-count { font-size: 14px; font-weight: 600; color: var(--text); margin-top: 4px; }
.coll-time { font-size: 11.5px; color: var(--muted); }
.coll-card p {
  margin: 6px 0 0;
  font-size: 11.5px; color: var(--muted);
  line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}

/* Items */
.kb-items { padding: 0; overflow: hidden; }
.items-head { padding: 16px 22px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.items-head h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }
.items-actions { display: flex; align-items: center; gap: 10px; }
.view-toggle { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.view-toggle button {
  width: 32px; height: 32px;
  border: none; background: var(--surface);
  color: var(--muted);
  cursor: pointer; display: grid; place-items: center;
}
.view-toggle button.active { background: var(--primary-soft); color: var(--primary); }

.items-table {}
.ih-row, .ii-row {
  display: grid;
  grid-template-columns: 2fr .8fr .8fr 1.2fr 1.2fr .6fr .8fr 50px;
  align-items: center;
  gap: 10px;
  padding: 12px 22px;
  font-size: 13px;
}
.ih-row {
  background: var(--surface-3);
  color: var(--text-soft);
  font-size: 12.5px;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}
.ii-row {
  border-bottom: 1px solid var(--border);
  transition: background .1s ease;
}
.ii-row:hover { background: var(--surface-2); }
.ii-row:last-child { border-bottom: none; }
.ii-name { display: flex; align-items: center; gap: 10px; min-width: 0; }
.ii-ico {
  width: 30px; height: 30px;
  border-radius: 6px;
  display: grid; place-items: center;
  font-size: 14px;
  flex-shrink: 0;
}
.ii-ico[data-color='blue']   { background: #dbeafe; }
.ii-ico[data-color='green']  { background: #dcfce7; }
.ii-ico[data-color='orange'] { background: #ffedd5; }
.ii-ico[data-color='pink']   { background: #fce7f3; }
.ii-ico[data-color='cyan']   { background: #cffafe; }
.ii-title { font-size: 13.5px; font-weight: 500; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 280px; }
.ii-sub { font-size: 11.5px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 280px; }
.ii-type, .ii-source { color: var(--muted); font-size: 12.5px; }
.ii-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.ii-tags .tag-more { background: var(--surface-3); color: var(--muted); }
.ii-time { color: var(--muted); font-size: 12px; }
.ii-usage { font-family: var(--t-mono); color: var(--text); font-weight: 600; font-size: 12.5px; }
.ii-actions { display: flex; gap: 4px; }
.td-ico-btn {
  width: 28px; height: 28px;
  border-radius: 6px;
  border: none; background: transparent;
  color: var(--muted); cursor: pointer;
  display: grid; place-items: center;
}
.td-ico-btn:hover { background: var(--surface-3); color: var(--primary); }
.tag i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; margin-right: 2px; }

.hist-pager { display: flex; align-items: center; justify-content: space-between; padding: 14px 22px; border-top: 1px solid var(--border); }
.pager-count { color: var(--muted); font-size: 12.5px; }
.pager-mid { display: flex; align-items: center; gap: 4px; }
.pager-mid button {
  min-width: 28px; height: 28px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-soft);
  font: inherit; font-size: 12.5px;
  border-radius: 6px;
  cursor: pointer; padding: 0 8px;
}
.pager-mid button.active { background: var(--primary); border-color: var(--primary); color: white; }
.pager-mid span { color: var(--muted-soft); padding: 0 4px; }
.pager-jump { font-size: 12.5px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.pager-jump input {
  width: 36px; height: 28px;
  border: 1px solid var(--border); border-radius: 6px;
  text-align: center; font: inherit; font-size: 12.5px;
  outline: none;
}

.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.link-mini { font-size: 12px; color: var(--primary); cursor: pointer; display: inline-flex; gap: 4px; align-items: center; }

.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.kpi-card {
  position: relative;
  padding: 14px;
  background: var(--surface-3);
  border-radius: 10px;
}
.kpi-ico {
  position: absolute; top: 12px; right: 12px;
  width: 26px; height: 26px;
  border-radius: 7px;
  display: grid; place-items: center;
  font-size: 13px;
}
.kpi-ico[data-color='blue']   { background: #dbeafe; color: #2563eb; }
.kpi-ico[data-color='green']  { background: #dcfce7; color: #16a34a; }
.kpi-ico[data-color='purple'] { background: #ede9fe; color: #7c3aed; }
.kpi-ico[data-color='orange'] { background: #ffedd5; color: #f97316; }
.kpi-value { font-size: 22px; font-weight: 700; color: var(--text); letter-spacing: -.015em; }
.kpi-label { font-size: 12px; color: var(--muted); margin-top: 2px; }
.kpi-sub { font-size: 11px; color: var(--muted-soft); margin-top: 4px; }

.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  border: none;
  font: inherit; font-size: 12px; font-weight: 500;
  cursor: pointer;
}
.tag-chip small { color: var(--muted); font-size: 11px; font-family: var(--t-mono); }
.tag-chip:hover { background: var(--primary); color: white; }
.tag-chip:hover small { color: rgba(255,255,255,.7); }

.recent-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 14px; }
.recent-list li { padding-bottom: 14px; border-bottom: 1px dashed var(--border); }
.recent-list li:last-child { border-bottom: none; padding-bottom: 0; }
.ru-title { font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.4; }
.ru-desc { font-size: 12px; color: var(--muted); margin-top: 4px; }
.ru-time { font-size: 11px; color: var(--muted-soft); margin-top: 4px; }

@media (max-width: 1400px) {
  .coll-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 1200px) {
  .kb-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .coll-grid { grid-template-columns: 1fr 1fr; }
}
</style>
