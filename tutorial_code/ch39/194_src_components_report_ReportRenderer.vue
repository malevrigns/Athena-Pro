<script setup lang="ts">
import { computed, ref, onMounted, onUpdated, useTemplateRef } from 'vue'
import { useCitations } from '@/composables/useCitations'
import { renderMarkdownWithCitations } from '@/utils/markdown'
import CitationsPanel from './CitationsPanel.vue'
import CitationMarker from './CitationMarker.vue'

const props = defineProps<{
  markdown: string
  metadata: { citations?: Citation[] } | null
}>()

// 当前被选中的引用编号(在主体和右栏间共享)
const activeNumber = ref<number | null>(null)

// composable 把 metadata.citations 数组变成响应式 Map
const { citationMap } = useCitations(() => props.metadata?.citations ?? [])

// Markdown → safe HTML(含 sup 占位)
const renderedHtml = computed(() => renderMarkdownWithCitations(props.markdown))

// 拿到 DOM 中所有 sup,挂载 CitationMarker 子组件
const bodyRef = useTemplateRef<HTMLElement>('bodyRef')
const supRefs = ref<HTMLElement[]>([])

// 每次 renderedHtml 变化,重新扫描 DOM 找 sup
function rescanSupElements() {
  if (!bodyRef.value) return
  supRefs.value = Array.from(
    bodyRef.value.querySelectorAll('sup[data-citation]')
  ) as HTMLElement[]
}

onMounted(rescanSupElements)
onUpdated(rescanSupElements)

// 用户在主体点击 [N] 时
function onCitationClick(num: number) {
  activeNumber.value = num
}
</script>

<template>
  <div class="grid grid-cols-12 gap-6">
    <!-- 主体 -->
    <article
      ref="bodyRef"
      class="col-span-8 prose prose-stone max-w-none"
      v-html="renderedHtml"
    />

    <!-- 用 Teleport 给每个 sup 挂一个 CitationMarker -->
    <CitationMarker
      v-for="el in supRefs"
      :key="el.dataset.citation"
      :target="el"
      :citation="citationMap.get(Number(el.dataset.citation))"
      :active="activeNumber === Number(el.dataset.citation)"
      @click="onCitationClick(Number(el.dataset.citation))"
    />

    <!-- 右侧来源面板 -->
    <aside class="col-span-4">
      <CitationsPanel
        :citations="metadata?.citations ?? []"
        :active-number="activeNumber"
        @select="activeNumber = $event"
      />
    </aside>
  </div>
</template>