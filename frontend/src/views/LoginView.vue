<template>
  <div class="login-wrap d-flex align-items-center justify-content-center min-vh-100">
    <div class="login-card card shadow-sm p-4" style="width:380px;max-width:95vw">
      <div class="text-center mb-4">
        <i class="bi bi-boxes text-primary" style="font-size:2.6rem"></i>
        <h5 class="mt-2 mb-0 fw-bold">WMS 倉儲管理系統</h5>
        <div class="text-muted small mt-1">請登入以繼續</div>
      </div>

      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="form-label">帳號</label>
          <input v-model="form.username" type="text" class="form-control"
                 placeholder="username" autocomplete="username" required />
        </div>
        <div class="mb-3">
          <label class="form-label">密碼</label>
          <div class="input-group">
            <input v-model="form.password" :type="showPwd ? 'text' : 'password'"
                   class="form-control" placeholder="password"
                   autocomplete="current-password" required />
            <button type="button" class="btn btn-outline-secondary" @click="showPwd = !showPwd">
              <i class="bi" :class="showPwd ? 'bi-eye-slash' : 'bi-eye'"></i>
            </button>
          </div>
        </div>
        <div class="mb-3 form-check">
          <input v-model="form.rememberMe" type="checkbox" class="form-check-input" id="remember-me" />
          <label class="form-check-label small text-muted" for="remember-me">記住我（30 天）</label>
        </div>
        <div v-if="errMsg" class="alert alert-danger py-2 small mb-3">{{ errMsg }}</div>
        <button type="submit" class="btn btn-primary w-100 py-2 fw-semibold" :disabled="loading">
          <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
          {{ loading ? '登入中…' : '登入' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCacheStore } from '@/stores/cache'

const router  = useRouter()
const route   = useRoute()
const auth    = useAuthStore()
const cache   = useCacheStore()
const loading = ref(false)
const errMsg  = ref('')
const showPwd = ref(false)

const form = reactive({ username: '', password: '', rememberMe: false })

async function submit() {
  errMsg.value  = ''
  loading.value = true
  try {
    await auth.login(form.username, form.password, form.rememberMe)
    // Prefetch common data in background
    cache.loadAll().catch(() => {})
    const redirect = (route.query.redirect as string) || '/admin/dashboard'
    router.push(redirect)
  } catch (e: any) {
    errMsg.value = e?.response?.data?.message ?? e?.message ?? '登入失敗，請確認帳號密碼'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { background: linear-gradient(135deg, #1a1d2e 0%, #2d3250 100%); }
.login-card { border-radius: 14px; border: none; }
</style>
