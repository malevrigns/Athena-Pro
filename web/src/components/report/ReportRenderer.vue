<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CopyDocument, Download, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import type { FinalReport } from '@/types/api'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ report: FinalReport | null; stream?: string }>()

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang, ignoreIllegals: true }).value}</code></pre>`
      } catch { /* fall through */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`
  },
})

const task = useTaskStore()
const session = useSessionStore()
const downloading = ref<string | null>(null)
const liveSource = computed(() => props.report?.markdown || props.stream || '')
const isStreaming = computed(() => !props.report && Boolean(props.stream))

const html = computed(() => {
  const raw = liveSource.value
  if (!raw) return ''
  return DOMPurify.sanitize(md.render(raw), { ADD_ATTR: ['target', 'rel'] })
})

const formats = computed(() => session.config?.export_formats || { md: true, html: true, pdf: false, docx: false })

watch(() => props.stream, () => {
  const el = document.querySelector('.report-body-scroll')
  if (el && isStreaming.value) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
})

async function download(fmt: 'md' | 'html' | 'pdf' | 'docx') {
  if (!task.current?.id) return
  if ((fmt === 'pdf' || fmt === 'docx') && !formats.value[fmt]) {
    ElMessage.warning(`${fmt.toUpperCase()} 服务端未启用 (缺 weasyprint/pandoc)`)
    return
  }
  downloading.value = fmt
  try {
    await task.downloadReport(fmt)
    ElMessage.success(`已下载 ${fmt.toUpperCase()}`)
  } catch (err) {
    ElMessage.error(`下载失败: ${(err as Error).message}`)
  } finally {
    downloading.value = null
  }
}

async function copyMarkdown() {
  if (!liveSource.value) return
  try {
    await navigator.clipboard.writeText(liveSource.value)
    ElMessage.success('已复制 Markdown')
  } catch (err) {
    ElMessage.error(`复制失败: ${(err as Error).message}`)
  }
}
</script>

<template>
  <ElCard shadow="never" class="athena-card report-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>研究报告</strong></div>
          <p class="subtitle">
            <span v-if="report">{{ report.citations.length }} 条引用 · 质量 {{ (report.quality?.overall ?? 0).toFixed(2) }}</span>
            <span v-else-if="isStreaming">Writer 撰写中…</span>
            <span v-else>等待 Writer 输出</span>
          </p>
        </div>
        <ElButtonGroup>
          <ElTooltip content="复制 Markdown" placement="top">
            <ElButton :icon="CopyDocument" :disabled="!liveSource" @click="copyMarkdown">复制</ElButton>
          </ElTooltip>
          <ElButton :icon="Document" :loading="downloading === 'md'" :disabled="!report" @click="download('md')">MD</ElButton>
          <ElButton :loading="downloading === 'html'" :disabled="!report" @click="download('html')">HTML</ElButton>
          <ElTooltip :content="formats.pdf ? '导出 PDF' : '服务端未安装 weasyprint'" placement="top">
            <ElButton :loading="downloading === 'pdf'" :disabled="!report || !formats.pdf" @click="download('pdf')">PDF</ElButton>
          </ElTooltip>
          <ElTooltip :content="formats.docx ? '导出 DOCX' : '服务端未安装 pandoc'" placement="top">
            <ElButton :loading="downloading === 'docx'" :disabled="!report || !formats.docx" @click="download('docx')">DOCX</ElButton>
          </ElTooltip>
        </ElButtonGroup>
      </div>
    </template>

    <ElScrollbar max-height="640px" class="report-body-scroll">
      <div v-if="liveSource" class="markdown-body" v-html="html" />
      <ElEmpty v-else :image-size="76" description="Writer 完成后, Markdown 与下载按钮会显示在这里">
        <ElButton plain :icon="Download" disabled>等待生成</ElButton>
      </ElEmpty>
    </ElScrollbar>
  </ElCard>
</template>

<style scoped>
.report-body-scroll { padding: 4px 8px; }
.markdown-body { font-size: 14.5px; color: var(--athena-text); padding-right: 8px; }
.markdown-body :deep(h1) {
  font-size: 26px; margin: 0 0 16px; padding-bottom: 10px;
  border-bottom: 2px solid var(--el-color-primary);
  font-weight: 800; letter-spacing: -.02em;
}
.markdown-body :deep(h2) {
  font-size: 19px; margin: 22px 0 10px;
  color: var(--el-color-primary);
  font-weight: 700;
}
.markdown-body :deep(h3) { font-size: 16px; margin: 16px 0 8px; font-weight: 700; }
.markdown-body :deep(p), .markdown-body :deep(li) { line-height: 1.85; color: var(--athena-text-soft); }
.markdown-body :deep(strong) { color: var(--athena-text); }
.markdown-body :deep(code) {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding: 2px 6px; border-radius: 5px; font-size: 90%;
  font-family: var(--athena-mono);
}
.markdown-body :deep(pre.hljs) {
  padding: 14px; border-radius: 10px;
  border: 1px solid var(--athena-border); margin: 12px 0; overflow: auto;
  background: var(--athena-surface-soft);
  font-family: var(--athena-mono);
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--el-color-primary);
  padding: 6px 14px;
  color: var(--athena-muted);
  margin: 10px 0;
  background: var(--el-color-primary-light-9);
  border-radius: 0 8px 8px 0;
}
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; }
.markdown-body :deep(table th) {
  background: var(--athena-surface-soft);
  border: 1px solid var(--athena-border);
  padding: 8px 12px;
  font-size: 13px; font-weight: 700;
  text-align: left;
}
.markdown-body :deep(table td) { border: 1px solid var(--athena-border); padding: 8px 12px; font-size: 13px; }
.markdown-body :deep(a) {
  color: var(--el-color-primary);
  border-bottom: 1px solid var(--el-color-primary-light-7);
  text-decoration: none;
}
</style>
