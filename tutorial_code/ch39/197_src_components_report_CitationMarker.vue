<script setup lang="ts">
import { computed } from 'vue'
import CitationPopover from './CitationPopover.vue'
import type { Citation } from '@/types/api'

const props = defineProps<{
  target: HTMLElement              // ReportRenderer 传来的目标 sup
  citation: Citation | undefined   // 该编号对应的 citation 数据
  active: boolean
}>()

const emit = defineEmits<{
  click: []
}>()

const num = computed(() => Number(props.target.dataset.citation))
</script>

<template>
  <!--
    Teleport: 把这个组件的渲染输出"投递"到 target 元素里。
    实际 DOM 结构变成:
      <sup data-citation="3">
        <CitationPopover>[3]</CitationPopover>
      </sup>
  -->
  <Teleport :to="target" :disabled="!citation">
    <CitationPopover :citation="citation" v-if="citation">
      <span
        :class="[
          'cursor-pointer rounded px-1 text-xs font-medium transition-colors',
          active
            ? 'bg-orange-200 text-orange-800'
            : 'bg-orange-100 text-orange-700 hover:bg-orange-200'
        ]"
        @click="emit('click')"
      >
        [{{ num }}]
      </span>
    </CitationPopover>
  </Teleport>
</template>