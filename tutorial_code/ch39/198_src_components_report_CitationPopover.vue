<script setup lang="ts">
import { NPopover } from 'naive-ui'
import { ExternalLink, Clock } from 'lucide-vue-next'
import type { Citation } from '@/types/api'
import { formatRelativeTime } from '@/utils/time'

defineProps<{
  citation: Citation
}>()
</script>

<template>
  <NPopover
    trigger="hover"
    placement="top"
    :delay="120"
    :duration="80"
    :width="384"
    raw
  >
    <template #trigger>
      <slot />
    </template>

    <div class="rounded-lg border border-stone-200 bg-white p-4
                shadow-lg ring-1 ring-black/5">
      <!-- 标题行 -->
      <div class="flex items-start justify-between gap-3 mb-2">
        <h4 class="font-semibold text-sm text-stone-900 leading-tight">
          {{ citation.title }}
        </h4>
        <a
          :href="citation.url"
          target="_blank"
          rel="noopener noreferrer"
          class="shrink-0 text-orange-600 hover:text-orange-700"
          @click.stop
        >
          <ExternalLink :size="16" />
        </a>
      </div>

      <!-- 原文摘录 -->
      <p class="text-xs text-stone-600 leading-relaxed mb-3 italic">
        "{{ citation.snippet }}"
      </p>

      <!-- 元信息 -->
      <div class="flex items-center gap-3 text-xs text-stone-400">
        <span class="truncate">{{ new URL(citation.url).hostname }}</span>
        <span v-if="citation.fetched_at" class="flex items-center gap-1">
          <Clock :size="12" />
          {{ formatRelativeTime(citation.fetched_at) }}
        </span>
      </div>
    </div>
  </NPopover>
</template>