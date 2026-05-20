<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import AppShell from '@/components/layout/AppShell.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()

function applyTheme(value: 'light' | 'dark') {
  document.documentElement.classList.toggle('dark', value === 'dark')
  document.documentElement.dataset.theme = value
  document.documentElement.style.colorScheme = value
}

onMounted(async () => {
  applyTheme(session.theme)
  await Promise.allSettled([session.refreshConfig(), session.refreshHealth()])
})

watch(() => session.theme, applyTheme)

const locale = computed(() => zhCn)
</script>

<template>
  <ElConfigProvider :locale="locale" namespace="el" size="default">
    <AppShell />
  </ElConfigProvider>
</template>
