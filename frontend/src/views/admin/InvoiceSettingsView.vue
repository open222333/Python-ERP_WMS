<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast   = useToastStore()
const loading = ref(false)
const saving  = ref(false)
const testing = ref(false)

const form = ref({
  enabled:     false,
  platform:    'ecpay',
  merchant_id: '',
  hash_key:    '',
  hash_iv:     '',
  seller_id:   '',
  test_mode:   true,
  tax_rate:    5,
  auto_issue:  false,
})

async function load() {
  loading.value = true
  try {
    const r = await http.get('/invoice/settings')
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
    await http.put('/invoice/settings', form.value)
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
  <div class="container-fluid py-3 px-4" style="max-width:700px">
    <h5 class="fw-bold mb-4">
      <i class="bi bi-receipt-cutoff me-2 text-primary"></i>電子發票設定
    </h5>

    <div v-if="loading" class="text-center text-muted py-5">
      <div class="spinner-border"></div>
    </div>

    <template v-else>

      <!-- 啟用開關 -->
      <div class="card shadow-sm mb-3">
        <div class="card-body d-flex align-items-center justify-content-between py-3">
          <div>
            <div class="fw-semibold">啟用電子發票</div>
            <small class="text-muted">關閉時不顯示發票相關選項</small>
          </div>
          <div class="form-check form-switch m-0">
            <input v-model="form.enabled" class="form-check-input" type="checkbox"
                   style="width:2.5em;height:1.3em;cursor:pointer" />
          </div>
        </div>
      </div>

      <!-- 平台設定 -->
      <div class="card shadow-sm mb-3">
        <div class="card-header py-2 fw-semibold small">
          <i class="bi bi-plug me-1"></i>串接平台
        </div>
        <div class="card-body">
          <div class="mb-3">
            <label class="form-label form-label-sm fw-semibold">發票平台</label>
            <select v-model="form.platform" class="form-select form-select-sm" style="max-width:200px">
              <option value="ecpay">綠界科技 (ECPay)</option>
            </select>
          </div>

          <div class="mb-3">
            <label class="form-label form-label-sm fw-semibold">
              特店編號 MerchantID <span class="text-danger">*</span>
            </label>
            <input v-model="form.merchant_id" type="text" class="form-control form-control-sm"
                   placeholder="例：3002599" style="max-width:240px" />
          </div>

          <div class="row g-3 mb-3">
            <div class="col-sm-6">
              <label class="form-label form-label-sm fw-semibold">
                HashKey <span class="text-danger">*</span>
              </label>
              <input v-model="form.hash_key" type="password" class="form-control form-control-sm"
                     placeholder="已設定則顯示 ******" autocomplete="new-password" />
            </div>
            <div class="col-sm-6">
              <label class="form-label form-label-sm fw-semibold">
                HashIV <span class="text-danger">*</span>
              </label>
              <input v-model="form.hash_iv" type="password" class="form-control form-control-sm"
                     placeholder="已設定則顯示 ******" autocomplete="new-password" />
            </div>
          </div>

          <div class="mb-3">
            <label class="form-label form-label-sm fw-semibold">賣方統一編號</label>
            <input v-model="form.seller_id" type="text" class="form-control form-control-sm"
                   placeholder="8 位數字" maxlength="8" style="max-width:160px" />
            <div class="form-text">開立 B2B 三聯式發票時使用</div>
          </div>
        </div>
      </div>

      <!-- 進階設定 -->
      <div class="card shadow-sm mb-3">
        <div class="card-header py-2 fw-semibold small">
          <i class="bi bi-sliders me-1"></i>進階設定
        </div>
        <div class="card-body">
          <div class="mb-3 d-flex align-items-center gap-3">
            <div class="form-check form-switch m-0">
              <input v-model="form.test_mode" class="form-check-input" type="checkbox"
                     id="testMode" style="width:2.2em;height:1.2em;cursor:pointer" />
              <label class="form-check-label fw-semibold" for="testMode">測試模式</label>
            </div>
            <small class="text-warning">
              <i class="bi bi-exclamation-triangle me-1"></i>
              測試模式使用 stage 環境，不會開立真實發票
            </small>
          </div>

          <div class="mb-3 d-flex align-items-center gap-3">
            <div class="form-check form-switch m-0">
              <input v-model="form.auto_issue" class="form-check-input" type="checkbox"
                     id="autoIssue" style="width:2.2em;height:1.2em;cursor:pointer" />
              <label class="form-check-label fw-semibold" for="autoIssue">POS 結帳後自動開立</label>
            </div>
            <small class="text-muted">開啟後，結帳時輸入的載具資訊將自動送出發票申請</small>
          </div>

          <div class="row g-2 align-items-center">
            <div class="col-auto">
              <label class="form-label form-label-sm fw-semibold mb-0">稅率（%）</label>
            </div>
            <div class="col-auto">
              <input v-model.number="form.tax_rate" type="number" min="0" max="100"
                     class="form-control form-control-sm" style="width:80px" />
            </div>
            <div class="col-auto"><small class="text-muted">目前台灣標準稅率 5%</small></div>
          </div>
        </div>
      </div>

      <!-- ECPay 說明 -->
      <div class="alert alert-info small mb-3">
        <strong><i class="bi bi-info-circle me-1"></i>申請方式：</strong>
        前往
        <a href="https://www.ecpay.com.tw" target="_blank" rel="noopener">ECPay 官網</a>
        申請電子發票加值服務，取得特店編號（MerchantID）、HashKey 及 HashIV 後填入上方。
        測試帳號請參考
        <a href="https://developers.ecpay.com.tw/?p=7372" target="_blank" rel="noopener">開發者文件</a>。
      </div>

      <div class="d-flex gap-2">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-floppy me-1"></i>儲存設定
        </button>
        <RouterLink to="/admin/invoices" class="btn btn-outline-secondary">
          <i class="bi bi-receipt-cutoff me-1"></i>查看發票記錄
        </RouterLink>
      </div>

    </template>
  </div>
</template>
