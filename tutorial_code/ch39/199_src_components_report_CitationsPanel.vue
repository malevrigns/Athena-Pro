<script setup lang="ts">
import { watch, useTemplateRef, nextTick } from 'vue'
import { ExternalLink } from 'lucide-vue-next'
import type { Citation } from '@/types/api'

const props = defineProps<{
  citations: Citation[]
  activeNumber: number | null
}>()

const emit = defineEmits<{
  select: [num: number]
}>()

const listRef = useTemplateRef<HTMLDivElement>('listRef')

// 选中变化时,滚动到对应项
watch(
  () => props.activeNumber,
  async (num) => {
    if (num == null) return
    await nextTick()
    const el = listRef.value?.querySelector(`[data-cite="${num}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
)
</script>

<template>
  <div class="sticky top-6">
    <h3 class="font-serif text-sm tracking-wider text-stone-500 uppercase mb-3">
      参考来源({{ citations.length }})
    </h3>

    <div
      ref="listRef"
      class="space-y-2 max-h-[calc(100vh-12rem)] overflow-y-auto pr-2"
    >
      <button
        v-for="c in citations"
        :key="c.number"
        :data-cite="c.number"
        :class="[
          'w-full text-left rounded-lg border p-3 transition-all',
          activeNumber === c.number
            ? 'border-orange-300 bg-orange-50 ring-1 ring-orange-200'
            : 'border-stone-200 bg-white hover:border-stone-300'
        ]"
        @click="emit('select', c.number)"
      >
        <div class="flex items-start gap-2">
          <span class="shrink-0 mt-0.5 inline-block w-5 h-5 rounded-full
                       bg-orange-100 text-orange-700 text-xs
                       font-semibold text-center leading-5">
            {{ c.number }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-stone-900 line-clamp-2">
              {{ c.title }}
            </p>
            <p class="mt-1 text-xs text-stone-500 truncate">
              {{ new URL(c.url).hostname }}
            </p>
          </div>
          <a
            :href="c.url"
            target="_blank"
            rel="noopener noreferrer"
            class="shrink-0 text-stone-400 hover:text-orange-600 mt-1"
            @click.stop
          >
            <ExternalLink :size="14" />
          </a>
        </div>
      </button>
    </div>
  </div>
</template>