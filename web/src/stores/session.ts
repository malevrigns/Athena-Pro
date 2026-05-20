import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { getConfig, getHealth } from '@/api/client'
import type { ConfigSnapshot, HealthSnapshot } from '@/types/api'

const LS = {
  apiKey: 'athena.apiKey',
  userId: 'athena.userId',
  budget: 'athena.budgetUsd',
  theme: 'athena.theme',
  themeMigration: 'athena.themeMigration.v5_3',
  preferredFormat: 'athena.exportFormat',
  apiBase: 'athena.apiBase',
}

// One-time migration: force light as the default for the new design-spec UI.
// Users can still flip to dark via the toggle.
if (typeof localStorage !== 'undefined' && !localStorage.getItem(LS.themeMigration)) {
  localStorage.setItem(LS.theme, 'light')
  localStorage.setItem(LS.themeMigration, '1')
}

export const useSessionStore = defineStore('session', () => {
  const apiKey = ref<string>(localStorage.getItem(LS.apiKey) || '')
  const userId = ref<string>(localStorage.getItem(LS.userId) || 'demo-user')
  const budgetUsd = ref<number>(Number(localStorage.getItem(LS.budget) || '5'))
  const theme = ref<'light' | 'dark'>((localStorage.getItem(LS.theme) as 'light' | 'dark') || 'light')
  const exportFormat = ref<'md' | 'html' | 'pdf' | 'docx'>((localStorage.getItem(LS.preferredFormat) as 'md' | 'html' | 'pdf' | 'docx') || 'md')
  const apiBase = ref(localStorage.getItem(LS.apiBase) || import.meta.env.VITE_API_BASE_URL || '')

  const config = ref<ConfigSnapshot | null>(null)
  const health = ref<HealthSnapshot | null>(null)
  const lastConnectionError = ref<string | null>(null)

  const displayName = computed(() => userId.value.replace(/^demo-/, ''))
  const isDark = computed(() => theme.value === 'dark')
  const hasApiKey = computed(() => apiKey.value.trim().length > 0)
  const isLive = computed(() => Boolean(config.value && config.value.llm_provider !== 'mock'))

  function save() {
    localStorage.setItem(LS.apiKey, apiKey.value)
    localStorage.setItem(LS.userId, userId.value)
    localStorage.setItem(LS.budget, String(budgetUsd.value))
    localStorage.setItem(LS.theme, theme.value)
    localStorage.setItem(LS.preferredFormat, exportFormat.value)
    localStorage.setItem(LS.apiBase, apiBase.value)
  }

  function setTheme(value: 'light' | 'dark') {
    theme.value = value
    localStorage.setItem(LS.theme, value)
    document.documentElement.dataset.theme = value
  }

  function toggleTheme() {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  async function refreshConfig() {
    try {
      config.value = await getConfig()
      lastConnectionError.value = null
    } catch (err) {
      lastConnectionError.value = err instanceof Error ? err.message : String(err)
    }
  }

  async function refreshHealth() {
    try {
      health.value = await getHealth()
      lastConnectionError.value = null
    } catch (err) {
      lastConnectionError.value = err instanceof Error ? err.message : String(err)
    }
  }

  watch(theme, (val) => {
    document.documentElement.dataset.theme = val
  }, { immediate: true })

  return {
    apiKey,
    userId,
    budgetUsd,
    theme,
    exportFormat,
    apiBase,
    config,
    health,
    lastConnectionError,
    displayName,
    isDark,
    hasApiKey,
    isLive,
    save,
    setTheme,
    toggleTheme,
    refreshConfig,
    refreshHealth,
  }
})
