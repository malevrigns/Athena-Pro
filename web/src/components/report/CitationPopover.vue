<script setup lang="ts">
import type { FinalReport } from '@/types/api'
defineProps<{ report: FinalReport | null; number: number }>()
</script>

<template>
  <ElPopover trigger="hover" :width="320">
    <template #reference>
      <sup class="citation-marker">[{{ number }}]</sup>
    </template>
    <div class="citation-popover">
      <strong>{{ report?.citations.find(c => c.number === number)?.title || 'Unknown source' }}</strong>
      <p>{{ report?.citations.find(c => c.number === number)?.quote }}</p>
    </div>
  </ElPopover>
</template>

<style scoped>
.citation-marker {
  color: var(--el-color-primary);
  font-weight: 600;
  cursor: help;
  padding: 0 2px;
}
.citation-popover strong { display: block; font-size: 13px; margin-bottom: 4px; }
.citation-popover p { margin: 0; color: var(--athena-muted); font-size: 12px; line-height: 1.55; }
</style>
