<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Link, Notebook, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useEntrance } from '@/composables/useAnime'
import {
  formatPaperMeta,
  formatScore,
  paperStatusMeta,
  PAPER_STATUS_OPTIONS,
  useProjectLiterature,
} from '@/composables/useProjectLiterature'
import type { Paper } from '@/types/research'

const props = defineProps<{ id: string }>()
const router = useRouter()
const literature = useProjectLiterature(() => props.id)
const {
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
  selectPaper,
} = literature

const SOURCE_LABELS: Record<string, string> = {
  llm_json: 'LLM JSON',
  fallback: '保守 fallback',
}

useEntrance('.literature-head, .tool-search, .literature-stats > div, .paper-form, .paper-list', { delay: (_el, i) => 80 + i * 70 })
useEntrance('.paper-row', { delay: (_el, i) => 260 + i * 35 })

onMounted(() => load())
watch(() => props.id, () => load())
watch(filter, () => loadPapers())

async function createPaper() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写论文标题')
    return
  }
  submitting.value = true
  try {
    await literature.createPaper()
    ElMessage.success('论文已加入项目')
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    submitting.value = false
  }
}

async function runPaperSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  searching.value = true
  try {
    const { created, skipped } = await literature.runPaperSearch()
    ElMessage.success(`检索完成,新增 ${created} 篇,跳过重复 ${skipped} 篇`)
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    searching.value = false
  }
}

async function createNote() {
  if (!selectedPaper.value) {
    ElMessage.warning('请先选择论文')
    return
  }
  try {
    await literature.createNote()
    ElMessage.success('阅读笔记已写入')
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

async function extractNote() {
  if (!selectedPaper.value) {
    ElMessage.warning('请先选择论文')
    return
  }
  extracting.value = true
  try {
    const { source } = await literature.extractNote()
    ElMessage.success(`PaperNote 已提取: ${SOURCE_LABELS[source] || source || 'unknown'}`)
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    extracting.value = false
  }
}
</script>

<template>
  <div class="literature-page">
    <section class="literature-head">
      <button class="back-btn" @click="router.push(`/projects/${props.id}`)">
        <ElIcon><ArrowLeft /></ElIcon>
      </button>
      <div>
        <div class="head-kicker">Literature</div>
        <h2>{{ store.current?.title || props.id }}</h2>
        <p>{{ store.current?.research_question || '—' }}</p>
      </div>
      <button class="icon-action" aria-label="刷新" @click="load">
        <ElIcon><Refresh /></ElIcon>
      </button>
    </section>

    <section class="card tool-search">
      <div>
        <div class="head-kicker">ToolRouter · paper_search</div>
        <h3>论文检索工具</h3>
        <p>通过统一工具协议执行,结果会写入论文库并进入项目 Trace。</p>
      </div>
      <div class="tool-controls">
        <ElInput v-model="searchQuery" :prefix-icon="Search" clearable placeholder="如 RAG baseline reproduction" @keyup.enter="runPaperSearch" />
        <ElInputNumber v-model="searchLimit" :min="1" :max="20" controls-position="right" />
        <button class="primary-btn" :disabled="searching" @click="runPaperSearch">
          <ElIcon><Search /></ElIcon>
          <span>{{ searching ? '检索中' : '检索' }}</span>
        </button>
      </div>
    </section>

    <section class="literature-stats">
      <div><span>论文</span><strong>{{ store.papers.length }}</strong></div>
      <div><span>纳入</span><strong>{{ includedCount }}</strong></div>
      <div><span>已读</span><strong>{{ readCount }}</strong></div>
      <div><span>有代码</span><strong>{{ withCodeCount }}</strong></div>
    </section>

    <section class="literature-grid">
      <form class="card paper-form" @submit.prevent="createPaper">
        <header>
          <div class="form-icon"><ElIcon><Plus /></ElIcon></div>
          <div>
            <h3>加入论文</h3>
            <p>结构化写入项目论文库</p>
          </div>
        </header>
        <ElInput v-model="form.title" placeholder="论文标题" maxlength="500" />
        <ElInput v-model="form.authorsText" type="textarea" :rows="3" placeholder="作者,逗号或换行分隔" />
        <div class="form-row">
          <ElInputNumber v-model="form.year" :min="1900" :max="2100" controls-position="right" placeholder="年份" />
          <ElInput v-model="form.venue" placeholder="Venue" />
        </div>
        <ElInput v-model="form.url" placeholder="论文 URL" />
        <ElInput v-model="form.pdf_url" placeholder="PDF URL" />
        <ElInput v-model="form.code_url" placeholder="代码仓库 URL" />
        <ElInput v-model="form.datasetText" type="textarea" :rows="3" placeholder="数据集,逗号或换行分隔" />
        <ElInput v-model="form.abstract" type="textarea" :rows="5" placeholder="Abstract / 摘要" />
        <div class="form-row">
          <ElSelect v-model="form.screening_status">
            <ElOption v-for="item in PAPER_STATUS_OPTIONS.slice(1)" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
          <ElInputNumber
            v-model="form.relevance_score"
            :min="0"
            :max="1"
            :step="0.05"
            controls-position="right"
            placeholder="相关性"
          />
        </div>
        <button class="primary-btn lg submit-btn" type="submit" :disabled="submitting">
          <ElIcon><Notebook /></ElIcon>
          <span>{{ submitting ? '写入中' : '加入论文库' }}</span>
        </button>
      </form>

      <section class="card note-panel">
        <header>
          <div class="form-icon"><ElIcon><Notebook /></ElIcon></div>
          <div>
            <h3>阅读笔记</h3>
            <p>{{ selectedPaper?.title || '选择一篇论文后记录 PaperNote' }}</p>
          </div>
        </header>
        <div v-if="selectedPaper" class="note-editor">
          <ElInput v-model="noteForm.problem" type="textarea" :rows="3" placeholder="Problem" />
          <ElInput v-model="noteForm.method" type="textarea" :rows="4" placeholder="Method" />
          <ElInput v-model="noteForm.training_setup" type="textarea" :rows="3" placeholder="Training / evaluation setup" />
          <div class="form-row">
            <ElInput v-model="noteForm.datasetsText" type="textarea" :rows="3" placeholder="Datasets,逗号或换行分隔" />
            <ElInput v-model="noteForm.metricsText" type="textarea" :rows="3" placeholder="Metrics,逗号或换行分隔" />
          </div>
          <ElInput v-model="noteForm.baselinesText" type="textarea" :rows="3" placeholder="Baselines,逗号或换行分隔" />
          <ElInput v-model="noteForm.main_results" type="textarea" :rows="3" placeholder="Main results" />
          <ElInput v-model="noteForm.limitations" type="textarea" :rows="3" placeholder="Limitations" />
          <ElInput v-model="noteForm.reproducibility_notes" type="textarea" :rows="3" placeholder="Reproducibility notes" />
          <ElInput v-model="noteForm.importantSectionsText" type="textarea" :rows="2" placeholder="Important sections,逗号或换行分隔" />
          <div class="note-actions">
            <button class="secondary-btn submit-btn" type="button" :disabled="extracting || store.notesLoading" @click="extractNote">
              <ElIcon><Notebook /></ElIcon>
              <span>{{ extracting ? '提取中' : 'AI 提取 PaperNote' }}</span>
            </button>
            <button class="primary-btn submit-btn" type="button" :disabled="store.notesLoading" @click="createNote">
              <ElIcon><Notebook /></ElIcon>
              <span>{{ store.notesLoading ? '写入中' : '保存 PaperNote' }}</span>
            </button>
          </div>
        </div>
        <ElEmpty v-else description="暂无选中论文" :image-size="72" />
      </section>

      <section class="card paper-list">
        <header class="list-head">
          <div>
            <h3>论文库</h3>
            <p>{{ papers.length }} / {{ store.papers.length }}</p>
          </div>
          <div class="list-actions">
            <ElInput v-model="query" :prefix-icon="Search" clearable placeholder="搜索标题、作者、数据集" />
            <ElSelect v-model="filter">
              <ElOption v-for="item in PAPER_STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
            </ElSelect>
          </div>
        </header>

        <div class="paper-table">
          <article
            v-for="paper in papers"
            :key="paper.id"
            class="paper-row"
            :class="{ active: selectedPaperId === paper.id }"
            @click="selectPaper(paper)"
          >
            <div class="paper-main">
              <div class="paper-title">{{ paper.title }}</div>
              <div class="paper-meta">{{ formatPaperMeta(paper) }}</div>
              <p v-if="paper.abstract">{{ paper.abstract }}</p>
              <div v-if="paper.dataset_mentions.length" class="paper-tags">
                <span v-for="dataset in paper.dataset_mentions" :key="dataset" class="tag tag-blue">{{ dataset }}</span>
              </div>
            </div>
            <div class="paper-side">
              <ElTag :type="paperStatusMeta(paper.screening_status).type">{{ paperStatusMeta(paper.screening_status).label }}</ElTag>
              <span class="score mono">score {{ formatScore(paper.relevance_score) }}</span>
              <a v-if="paper.url" :href="paper.url" target="_blank" rel="noreferrer">
                <ElIcon><Link /></ElIcon>
                <span>论文</span>
              </a>
              <a v-if="paper.code_url" :href="paper.code_url" target="_blank" rel="noreferrer">
                <ElIcon><Link /></ElIcon>
                <span>代码</span>
              </a>
            </div>
          </article>
          <ElEmpty v-if="!papers.length" description="暂无论文" :image-size="92" />
        </div>
      </section>
    </section>

    <section v-if="selectedPaper" class="card notes-list">
      <header class="list-head">
        <div>
          <h3>已记录 PaperNote</h3>
          <p>{{ selectedPaper.title }}</p>
        </div>
        <ElTag>{{ selectedNotes.length }}</ElTag>
      </header>
      <div class="note-list-body">
        <article v-for="note in selectedNotes" :key="note.id" class="note-card">
          <h4>{{ note.problem || '未填写 problem' }}</h4>
          <p v-if="note.method">{{ note.method }}</p>
          <dl>
            <div><dt>Datasets</dt><dd>{{ note.datasets.join(', ') || '—' }}</dd></div>
            <div><dt>Metrics</dt><dd>{{ note.metrics.join(', ') || '—' }}</dd></div>
            <div><dt>Baselines</dt><dd>{{ note.baselines.join(', ') || '—' }}</dd></div>
          </dl>
          <p v-if="note.reproducibility_notes" class="repro">{{ note.reproducibility_notes }}</p>
        </article>
        <ElEmpty v-if="!selectedNotes.length" description="还没有阅读笔记" :image-size="72" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.literature-page { display: grid; gap: 18px; }
.literature-head {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 18px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 38px;
  gap: 16px;
  align-items: center;
}
.back-btn,
.icon-action {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}
.back-btn:hover,
.icon-action:hover {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: var(--primary-line);
}
.head-kicker {
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.literature-head h2 { margin: 3px 0; font-size: 22px; }
.literature-head p { margin: 0; color: var(--muted); }
.tool-search {
  padding: 16px;
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(420px, 620px);
  gap: 16px;
  align-items: center;
}
.tool-search h3 {
  margin: 3px 0;
  font-size: 16px;
}
.tool-search p {
  margin: 0;
  color: var(--muted);
}
.tool-controls {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 110px 92px;
  gap: 10px;
}
.literature-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.literature-stats > div {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  padding: 14px 16px;
  display: grid;
  gap: 4px;
}
.literature-stats span { color: var(--muted); font-size: 12px; }
.literature-stats strong { font-size: 24px; line-height: 1; }
.literature-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.paper-form,
.note-panel,
.paper-list {
  padding: 20px;
}
.paper-form {
  display: grid;
  gap: 12px;
}
.paper-form header,
.note-panel header,
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.paper-form header { justify-content: flex-start; }
.note-panel header { justify-content: flex-start; }
.paper-form h3,
.note-panel h3,
.paper-list h3 { margin: 0; font-size: 16px; }
.paper-form p,
.note-panel p,
.paper-list p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.form-icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.submit-btn { width: 100%; justify-content: center; }
.note-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.secondary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid var(--primary-line);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all .12s ease;
}
.secondary-btn:hover {
  background: color-mix(in srgb, var(--primary-soft) 74%, white);
}
.secondary-btn:disabled,
.primary-btn:disabled {
  cursor: not-allowed;
  opacity: .58;
}
.note-editor {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}
.list-actions {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 130px;
  gap: 10px;
  min-width: 380px;
}
.paper-table { margin-top: 16px; display: grid; gap: 12px; }
.paper-row {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 128px;
  gap: 16px;
  background: var(--surface);
  cursor: pointer;
}
.paper-row.active {
  border-color: var(--primary-line);
  background: var(--primary-soft);
}
.paper-title {
  font-weight: 700;
  color: var(--text);
}
.paper-meta {
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
}
.paper-main p {
  margin: 10px 0 0;
  color: var(--text-soft);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.paper-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.paper-side {
  display: grid;
  align-content: start;
  justify-items: end;
  gap: 8px;
}
.score { color: var(--muted); font-size: 12px; }
.paper-side a {
  height: 26px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--primary);
  font-weight: 600;
  font-size: 12px;
}
.notes-list { padding: 20px; }
.note-list-body {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}
.note-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  background: var(--surface);
}
.note-card h4 {
  margin: 0;
  font-size: 15px;
}
.note-card p {
  margin: 8px 0 0;
  color: var(--text-soft);
}
.note-card dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0 0;
}
.note-card dt { color: var(--muted); font-size: 12px; }
.note-card dd { margin: 3px 0 0; overflow-wrap: anywhere; }
.note-card .repro {
  border-top: 1px solid var(--border);
  padding-top: 10px;
}
@media (max-width: 1120px) {
  .literature-grid { grid-template-columns: 1fr; }
  .literature-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tool-search { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .literature-stats,
  .form-row,
  .list-actions,
  .tool-controls,
  .note-card dl,
  .paper-row { grid-template-columns: 1fr; }
  .list-actions { min-width: 0; }
  .paper-side { justify-items: start; }
  .note-actions { grid-template-columns: 1fr; }
}
</style>
