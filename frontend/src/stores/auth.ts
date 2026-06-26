import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import http from '@/api'
import type { Role, MeResponse, Store } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // ── state ──────────────────────────────────────────────
  const token        = ref<string | null>(localStorage.getItem('token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))
  const username     = ref<string | null>(null)
  const role         = ref<Role | null>(null)
  const storeIds     = ref<string[]>([])
  const templateId   = ref<string | null>(null)
  const pagesEnabled = ref<Record<string, boolean> | null>(null)
  const ready        = ref(false)   // /auth/me 是否已完成

  // ── 店家脈絡 ───────────────────────────────────────────
  const storeList     = ref<Store[]>([])          // 使用者可存取的店家清單
  const activeStoreId = ref<string | null>(null)  // 目前作業店家（依 POS 設定為主）

  const activeStore = computed<Store | null>(
    () => storeList.value.find(s => s._id === activeStoreId.value) ?? null
  )
  const activeStoreName = computed<string>(
    () => activeStore.value?.name ?? ''
  )

  // ── getters ────────────────────────────────────────────
  const isLoggedIn   = computed(() => !!token.value)
  const isSuperAdmin = computed(() => role.value === 'super_admin')
  const isAdmin      = computed(() => role.value === 'admin' || role.value === 'super_admin')

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
    storeIds.value = res.data.store_ids ?? []
    await fetchMe()
    return res.data as { success: boolean; role: Role }
  }

  async function fetchMe() {
    try {
      const [meRes, storesRes, settingsRes] = await Promise.allSettled([
        http.get<MeResponse>('/auth/me'),
        http.get('/store/'),
        http.get('/settings/'),
      ])

      if (meRes.status === 'fulfilled') {
        const d = meRes.value.data
        username.value     = d.username
        role.value         = d.role
        storeIds.value     = d.store_ids ?? []
        templateId.value   = d.template_id
        pagesEnabled.value = d.pages_enabled
      }

      // 建立可存取店家清單
      if (storesRes.status === 'fulfilled') {
        const all: Store[] = storesRes.value.data.data ?? []
        storeList.value = storeIds.value.length
          ? all.filter(s => storeIds.value.includes(s._id))
          : all   // super_admin 可看全部
      }

      // 以 pos_default_store_id 設定為目前作業店家
      if (settingsRes.status === 'fulfilled') {
        const posStoreId: string | null = settingsRes.value.data.data?.pos_default_store_id ?? null
        if (posStoreId && storeList.value.some(s => s._id === posStoreId)) {
          activeStoreId.value = posStoreId
        } else if (storeList.value.length > 0) {
          activeStoreId.value = storeList.value[0]._id
        }
      }
    } finally {
      ready.value = true
    }
  }

  /** 切換作業店家（管理員：同時儲存至系統設定） */
  async function setActiveStore(id: string) {
    activeStoreId.value = id
    if (isAdmin.value) {
      await http.put('/settings/', { pos_default_store_id: id || null })
    }
  }

  function logout() {
    token.value        = null
    refreshToken.value = null
    username.value     = null
    role.value         = null
    storeIds.value     = []
    storeList.value    = []
    activeStoreId.value = null
    pagesEnabled.value = null
    ready.value        = false
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  return {
    token, username, role, storeIds, templateId, pagesEnabled, ready,
    storeList, activeStoreId, activeStore, activeStoreName,
    isLoggedIn, isSuperAdmin, isAdmin,
    pageVisible, login, fetchMe, logout, setActiveStore,
  }
})
