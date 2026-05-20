import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { http } from '@/utils/http'

interface SessionInfo {
  session_id: string
  user_id: string
  total_cost_usd: number
  preferences: Record
}

export const useSessionStore = defineStore('session', () => {
  // ===== State =====
  const token = ref(localStorage.getItem('athena_token'))
  const info = ref(null)
  const loading = ref(false)
  
  // ===== Getters =====
  const isAuthenticated = computed(() => token.value !== null)
  const userName = computed(() => info.value?.user_id ?? 'Guest')
  
  // ===== Actions =====
  async function tryAutoLogin() {
    if (!token.value) return false
    try {
      info.value = await http('/v1/sessions/current')
      return true
    } catch {
      logout()
      return false
    }
  }
  
  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await http<{ token: string; session: SessionInfo }>(
        '/v1/auth/login',
        { method: 'POST', body: { username, password } },
      )
      token.value = res.token
      info.value = res.session
      localStorage.setItem('athena_token', res.token)
    } finally {
      loading.value = false
    }
  }
  
  function logout() {
    token.value = null
    info.value = null
    localStorage.removeItem('athena_token')
  }
  
  async function refreshCost() {
    if (!info.value) return
    info.value = await http('/v1/sessions/current')
  }
  
  return {
    // state
    token, info, loading,
    // getters
    isAuthenticated, userName,
    // actions
    tryAutoLogin, login, logout, refreshCost,
  }
})