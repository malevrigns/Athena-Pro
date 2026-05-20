<script setup lang="ts">
defineProps<{
  content: string
  showCursor: boolean
}>()
</script>

<template>
  <div class="prose prose-stone max-w-none">
    <div class="text-xs uppercase tracking-wider text-stone-400 mb-2">
      AI 正在思考
    </div>
    <pre class="whitespace-pre-wrap font-sans text-stone-700 leading-relaxed">{{ content }}<span
        v-if="showCursor"
        class="inline-block h-4 w-2 bg-orange-500 animate-pulse ml-1"
      /></pre>
  </div>
</template>