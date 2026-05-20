<script setup lang="ts">
import { computed } from 'vue'
import { Link } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'

const task = useTaskStore()
const sources = computed(() => task.sources.slice(0, 12))
</script>

<template>
  <ElCard shadow="never" class="athena-card">
    <template #header>
      <div class="athena-card-head">
        <div>
          <div class="title"><strong>来源池</strong></div>
          <p class="subtitle">Researcher 收集到的所有原始 URL</p>
        </div>
        <ElTag round size="small" effect="plain">{{ sources.length }} 源</ElTag>
      </div>
    </template>

    <ElEmpty v-if="!sources.length" description="Researcher 完成后展示原始 URL" :image-size="56" />
    <ElScrollbar v-else max-height="380px">
      <div class="source-list">
        <div v-for="s in sources" :key="s.source_id" class="source-row">
          <strong>{{ s.title }}</strong>
          <p>{{ s.snippet || '(未提供摘要)' }}</p>
          <ElLink :href="s.url" target="_blank" :icon="Link" :underline="false" type="info">{{ s.url }}</ElLink>
        </div>
      </div>
    </ElScrollbar>
  </ElCard>
</template>

<style scoped>
.source-list { display: grid; gap: 10px; }
.source-row { padding: 10px 12px; border: 1px solid var(--athena-border); border-radius: 8px; background: var(--athena-surface-soft); display: grid; gap: 4px; }
.source-row strong { font-size: 13px; }
.source-row p { margin: 0; color: var(--athena-muted); font-size: 12px; line-height: 1.5; }
.source-row :deep(.el-link) { font-family: var(--athena-mono); font-size: 11px; }
</style>
