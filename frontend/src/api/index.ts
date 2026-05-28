import axios, { type AxiosRequestConfig } from 'axios'

const http = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

// ── 請求攔截：帶入 JWT ─────────────────────────────────
http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')

  // ── DEBUG（排錯用，確認 token 後可刪除）──────────────
  console.debug(
    `[http] ${(cfg.method ?? 'GET').toUpperCase()} ${cfg.url}`,
    token ? `token=${token.slice(0, 20)}…` : '⚠️ NO TOKEN',
  )
  // ────────────────────────────────────────────────────

  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// ── 回應攔截：401 時嘗試 refresh token ────────────────
let _refreshing = false
let _queue: Array<(token: string) => void> = []

/**
 * 401 後無法 refresh → 清除 token 並派送自定義事件。
 * 由 AdminLayout 或 App.vue 監聽 'app:unauthorized' 執行
 * router.push('/login')，避免 window.location.href 造成的
 * 整頁重載迴圈。
 */
function _handleUnauthorized() {
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  // 若已在登入頁則不重複派送
  if (window.location.pathname !== '/login') {
    window.dispatchEvent(new CustomEvent('app:unauthorized'))
  }
}

http.interceptors.response.use(
  res => res,
  async err => {
    const original: AxiosRequestConfig & { _retry?: boolean } = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refreshToken')
      if (refreshToken) {
        if (_refreshing) {
          return new Promise(resolve => {
            _queue.push(token => {
              original.headers!['Authorization'] = `Bearer ${token}`
              resolve(http(original))
            })
          })
        }
        _refreshing = true
        try {
          const res = await axios.post('/auth/refresh', {}, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          })
          const newToken: string = res.data.token
          localStorage.setItem('token', newToken)
          _queue.forEach(cb => cb(newToken))
          _queue = []
          original.headers!['Authorization'] = `Bearer ${newToken}`
          return http(original)
        } catch {
          _handleUnauthorized()
        } finally {
          _refreshing = false
        }
      } else {
        _handleUnauthorized()
      }
    }
    return Promise.reject(err)
  }
)

export default http
