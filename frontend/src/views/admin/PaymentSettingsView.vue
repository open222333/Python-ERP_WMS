<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast   = useToastStore()
const loading = ref(false)
const saving  = ref(false)

const form = ref({
  enabled:        false,
  channel_id:     '',
  channel_secret: '',
  sandbox:        true,
})

async function load() {
  loading.value = true
  try {
    const r = await http.get('/pos/linepay-settings')
    Object.assign(form.value, r.data.data || {})
  } catch {
    toast.show('載入設定失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/pos/linepay-settings', form.value)
    toast.show('設定已儲存', 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container-fluid py-3 px-4" style="max-width:680px">
    <h5 class="fw-bold mb-4">
      <i class="bi bi-wallet2 me-2 text-success"></i>LINE Pay 全支付設定
    </h5>

    <div v-if="loading" class="text-center text-muted py-5">
      <div class="spinner-border"></div>
    </div>

    <template v-else>

      <!-- 啟用 -->
      <div class="card shadow-sm mb-3">
        <div class="card-body d-flex align-items-center justify-content-between py-3">
          <div>
            <div class="fw-semibold">啟用 LINE Pay 全支付</div>
            <small class="text-muted">啟用後 POS 付款方式將自動加入「LINE Pay」選項</small>
          </div>
          <div class="form-check form-switch m-0">
            <input v-model="form.enabled" class="form-check-input" type="checkbox"
                   style="width:2.5em;height:1.3em;cursor:pointer" />
          </div>
        </div>
      </div>

      <!-- Channel 設定 -->
      <div class="card shadow-sm mb-3">
        <div class="card-header py-2 fw-semibold small">
          <i class="bi bi-key me-1"></i>Channel 金鑰
        </div>
        <div class="card-body">
          <div class="mb-3">
            <label class="form-label form-label-sm fw-semibold">
              Channel ID <span class="text-danger">*</span>
            </label>
            <input v-model="form.channel_id" type="text" class="form-control form-control-sm"
                   placeholder="例：1234567890" style="max-width:260px" />
          </div>
          <div class="mb-3">
            <label class="form-label form-label-sm fw-semibold">
              Channel Secret <span class="text-danger">*</span>
            </label>
            <input v-model="form.channel_secret" type="password" class="form-control form-control-sm"
                   placeholder="已設定則顯示 ******" autocomplete="new-password" style="max-width:360px" />
          </div>
          <div class="d-flex align-items-center gap-3">
            <div class="form-check form-switch m-0">
              <input v-model="form.sandbox" class="form-check-input" type="checkbox"
                     id="sandbox" style="width:2.2em;height:1.2em;cursor:pointer" />
              <label class="form-check-label fw-semibold" for="sandbox">Sandbox 測試模式</label>
            </div>
            <small class="text-warning">
              <i class="bi bi-exclamation-triangle me-1"></i>
              沙盒模式不扣真實款項
            </small>
          </div>
        </div>
      </div>

      <!-- 付款流程說明 -->
      <div class="card shadow-sm mb-3">
        <div class="card-header py-2 fw-semibold small">
          <i class="bi bi-info-circle me-1"></i>付款流程（CPM 模式）
        </div>
        <div class="card-body">
          <ol class="mb-0 small text-muted ps-3" style="line-height:2">
            <li>顧客開啟 LINE Pay App → 點選「付款」→ 出示條碼</li>
            <li>收銀員用條碼掃描器掃描顧客螢幕上的條碼</li>
            <li>POS 自動向 LINE Pay 發送扣款請求</li>
            <li>扣款成功後才記錄銷售訂單</li>
            <li>退款時系統自動呼叫 LINE Pay 退款 API</li>
          </ol>
        </div>
      </div>

      <!-- 申請連結 -->
      <div class="alert alert-info small mb-3">
        <strong><i class="bi bi-box-arrow-up-right me-1"></i>申請 LINE Pay 商家帳號：</strong>
        前往
        <a href="https://pay.line.me/tw/developers/main/introduce" target="_blank" rel="noopener">LINE Pay Developers</a>
        建立 Merchant 帳號，於後台取得 Channel ID 與 Channel Secret 後填入上方。
      </div>

      <div class="d-flex gap-2">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-floppy me-1"></i>儲存設定
        </button>
        <RouterLink to="/admin/pos-sales" class="btn btn-outline-secondary">
          <i class="bi bi-receipt me-1"></i>查看銷售記錄
        </RouterLink>
      </div>

    </template>
  </div>
</template>
