import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import http from '@/api'
import type { Role, MeResponse } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // ── state ──────────────────────────────────────────────
  const token        = ref<string | null>(localStorage.getItem('token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))
  const username     = ref<string | null>(null)
  const role         = ref<Role | null>(null)
  const templateId   = ref<string | null>(null)
  const pagesEnabled = ref<Record<string, boolean> | null>(null)
  const ready        = ref(false)   // /auth/me 是否已完成

  // ── getters ────────────────────────────────────────────
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin    = computed(() => role.value === 'admin')

  /** 某頁面是否可顯示（null = 無限制，全部顯示） */
  function pageVisible(key: string): boolean {
    if (!pagesEnabled.value) return true
    return pagesEnabled.value[key] !== false
  }

  // ── actions ────────────────────────────────────────────
  async function login(user: string, pwd: string, rememberMe = false) {
    const res = await http.post('/auth/login', {
      username: user, password: pwd, remember_me: rememberMe,
    })
    token.value = res.data.token
    localStorage.setItem('token', res.data.token)
    if (rememberMe && res.data.refresh_token) {
      refreshToken.value = res.data.refresh_token
      localStorage.setItem('refreshToken', res.data.refresh_token)
    }
    await fetchMe()
    return res.data as { success: boolean; role: Role }
  }

  async function fetchMe() {
    try {
      const res = await http.get<MeResponse>('/auth/me')
      const d = res.data
      username.value     = d.username
      role.value         = d.role
      templateId.value   = d.template_id
      pagesEnabled.value = d.pages_enabled
    } finally {
      ready.value = true
    }
  }

  function logout() {
    token.value        = null
    refreshToken.value = null
    username.value     = null
    role.value         = null
    pagesEnabled.value = null
    ready.value        = false
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  return {
    token, username, role, templateId, pagesEnabled, ready,
    isLoggedIn, isAdmin,
    pageVisible, login, fetchMe, logout,
  }
})
