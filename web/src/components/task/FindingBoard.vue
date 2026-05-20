<script setup lang="ts">
import { Link } from '@element-plus/icons-vue'
import type { Finding } from '@/types/api'

defineProps<{ findings: Finding[] }>()
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>研究发现</strong></div>
          <p class="subtitle">每个 finding 含 LLM 摘要、证据片段、来源 URL 与置信度</p>
        </div>
        <ElTag round size="small" type="success" effect="light">{{ findings.length }} findings</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!findings.length" description="Researcher 完成调研后在这里展示 finding 与证据" :image-size="64" />
    <ElCollapse v-else accordion>
      <ElCollapseItem
        v-for="finding in findings"
        :key="finding.id"
        :name="finding.id"
      >
        <template #title>
          <div class="finding-title">
            <strong>{{ finding.title }}</strong>
            <ElTag size="small" type="warning" effect="plain" round>置信 {{ finding.confidence.toFixed(2) }}</ElTag>
            <ElTag size="small" effect="plain" round>{{ finding.sources.length }} 来源</ElTag>
          </div>
        </template>
        <p class="finding-summary">{{ finding.summary }}</p>
        <ElDivider v-if="finding.evidence?.length" content-position="left">证据片段</ElDivider>
        <ul v-if="finding.evidence?.length" class="evidence-list">
          <li v-for="(e, i) in finding.evidence" :key="i">{{ e }}</li>
        </ul>
        <ElDivider v-if="finding.sources.length" content-position="left">来源链接</ElDivider>
        <ul class="source-list">
          <li v-for="src in finding.sources" :key="src.id">
            <ElLink :href="src.url" target="_blank" type="primary" :underline="false" :icon="Link">
              {{ src.title }}
            </ElLink>
            <code>{{ src.url }}</code>
          </li>
        </ul>
      </ElCollapseItem>
    </ElCollapse>
  </ElCard>
</template>

<style scoped>
.finding-title { display: flex; align-items: center; gap: 8px; }
.finding-title strong { font-weight: 600; }
.finding-summary {
  margin: 0 0 8px;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--athena-text-soft);
}
.evidence-list, .source-list { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
.evidence-list li {
  color: var(--athena-muted);
  font-size: 12.5px;
  line-height: 1.55;
}
.source-list li {
  list-style: none;
  margin-left: -18px;
  padding: 8px 12px;
  background: var(--athena-surface-soft);
  border: 1px solid var(--athena-border);
  border-radius: 8px;
  display: grid;
  gap: 4px;
}
.source-list code {
  font-family: var(--athena-mono);
  font-size: 11px;
  color: var(--athena-muted);
  word-break: break-all;
}
</style>
