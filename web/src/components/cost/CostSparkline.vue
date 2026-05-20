<script setup lang="ts">
defineProps<{ values: number[] }>()
</script>

<template>
  <svg class="sparkline" viewBox="0 0 120 36" aria-hidden="true">
    <polyline :points="values.map((v, i) => `${i * (120 / Math.max(values.length - 1, 1))},${34 - v * 30}`).join(' ')" fill="none" stroke="currentColor" stroke-width="3" />
  </svg>
</template>
