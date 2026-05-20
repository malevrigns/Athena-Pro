<script setup lang="ts">
import { Link } from '@element-plus/icons-vue'
import type { FinalReport } from '@/types/api'

defineProps<{ report: FinalReport | null }>()
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>引用追溯</strong></div>
          <p class="subtitle">报告中所有 [n] 标记对应的来源</p>
        </div>
        <ElTag round size="small" type="primary" effect="light">{{ report?.citations.length || 0 }} 条</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!report?.citations.length" description="报告完成后, 这里显示每条来源的标题与 URL" :image-size="56" />
    <ElScrollbar v-else max-height="540px">
      <div class="citation-list">
        <div v-for="c in report.citations" :key="c.number" class="citation-row">
          <div class="num">[{{ c.number }}]</div>
          <div class="body">
            <ElLink :href="c.url" target="_blank" type="primary" :icon="Link" :underline="false">{{ c.title }}</ElLink>
            <code>{{ c.url }}</code>
            <p v-if="c.quote">{{ c.quote }}</p>
          </div>
        </div>
      </div>
    </ElScrollbar>
  </ElCard>
</template>

<style scoped>
.citation-list { display: grid; gap: 10px; }
.citation-row { display: grid; grid-template-columns: 38px 1fr; gap: 10px; padding: 10px 12px; border: 1px solid var(--athena-border); border-radius: 8px; background: var(--athena-surface-soft); }
.citation-row .num { font-family: var(--athena-mono); font-weight: 700; color: var(--el-color-primary); }
.citation-row .body { display: grid; gap: 4px; min-width: 0; }
.citation-row code {
  font-family: var(--athena-mono);
  font-size: 11px;
  color: var(--athena-muted);
  word-break: break-all;
}
.citation-row p { margin: 0; font-size: 12px; color: var(--athena-muted); line-height: 1.55; }
</style>
