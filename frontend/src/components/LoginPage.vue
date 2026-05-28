<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth  = useAuthStore()
const toast = useToastStore()

const username = ref('')
const password = ref('')
const remember = ref(true)
const loading  = ref(false)
const error    = ref('')

async function doLogin() {
  if (!username.value || !password.value) {
    error.value = '請輸入帳號與密碼'
    return
  }
  loading.value = true
  error.value   = ''
  try {
    await auth.login(username.value.trim(), password.value, remember.value)
  } catch (e) {
    error.value = e?.response?.data?.message || e.message || '登入失敗'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-overlay">
    <div class="login-box">
      <div class="login-logo">
        <i class="bi bi-boxes"></i>
        <h4>WMS 倉儲管理系統</h4>
      </div>

      <div v-if="error" class="alert alert-danger py-2 small">{{ error }}</div>

      <div class="mb-3">
        <input
          v-model="username"
          type="text"
          class="form-control"
          placeholder="帳號"
          autocomplete="username"
          @keydown.enter="doLogin"
        />
      </div>
      <div class="mb-3">
        <input
          v-model="password"
          type="password"
          class="form-control"
          placeholder="••••••••"
          autocomplete="current-password"
          @keydown.enter="doLogin"
        />
      </div>
      <div class="mb-3 form-check">
        <input v-model="remember" type="checkbox" class="form-check-input" id="chk-remember" />
        <label class="form-check-label small text-muted" for="chk-remember">記住我 30 天</label>
      </div>
      <button
        class="btn btn-primary w-100 fw-semibold py-2"
        :disabled="loading"
        @click="doLogin"
      >
        <span v-if="loading" class="spinner-border spinner-border-sm me-1"></span>
        登入
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-overlay {
  position: fixed; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg,#1a1d2e 0%,#2d3250 100%);
  z-index: 9999;
}
.login-box {
  background: #fff; border-radius: 16px; padding: 40px 36px;
  width: 360px; box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.login-logo { text-align: center; margin-bottom: 28px; }
.login-logo i { font-size: 3rem; color: var(--accent); display: block; }
.login-logo h4 { font-weight: 700; margin-top: 8px; color: #1a1d2e; }
</style>
