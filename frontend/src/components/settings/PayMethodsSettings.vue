<!-- [U10] 自 views/admin/SettingsView.vue 拆出 -->
<script setup lang="ts">
// POS 付款方式＋LINE Pay＋全支付。三者資料各有獨立端點，由本元件自行載入
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

interface PayMethod {
  id:         string
  label:      string
  enabled:    boolean
  has_cash:   boolean
  sort_order: number
  _isNew?:    boolean
}

const toast = useToastStore()

const payMethods = ref<PayMethod[]>([])
const savingPay  = ref(false)

const linePayEnabled  = ref(false)
const linePayChId     = ref('')
const linePaySecret   = ref('')
const linePaySandbox  = ref(true)
const savingLinePay   = ref(false)

const zPayEnabled  = ref(false)
const zPayMchId    = ref('')
const zPaySecret   = ref('')
const zPaySandbox  = ref(true)
const savingZPay   = ref(false)

function applyLinePay(lp: Record<string, any>) {
  linePayEnabled.value = !!lp.enabled
  linePayChId.value    = lp.channel_id || ''
  linePaySecret.value  = lp.channel_secret || ''
  linePaySandbox.value = lp.sandbox ?? true
}

function applyZPay(zp: Record<string, any>) {
  zPayEnabled.value = !!zp.enabled
  zPayMchId.value   = zp.merchant_id || ''
  zPaySecret.value  = zp.merchant_secret || ''
  zPaySandbox.value = zp.sandbox ?? true
}

async function load() {
  try {
    const [pmR, lpR, zpR] = await Promise.all([
      http.get('/pos/payment-methods'),
      http.get('/pos/linepay-settings'),
      http.get('/pos/zpay-settings'),
    ])
    // payment methods — fallback to cash if empty
    const pm: PayMethod[] = pmR.data?.data || []
    payMethods.value = pm.length ? pm : [
      { id: 'cash', label: '現金', enabled: true, has_cash: true, sort_order: 0 }
    ]
    applyLinePay(lpR.data?.data || {})
    applyZPay(zpR.data?.data || {})
  } catch {
    toast.show('載入付款設定失敗', 'danger')
  }
}

function addPayMethodRow() {
  const maxSort = payMethods.value.reduce((m, x) => Math.max(m, x.sort_order), -1)
  payMethods.value.push({
    id:         '',
    label:      '',
    enabled:    true,
    has_cash:   false,
    sort_order: maxSort + 1,
    _isNew:     true,
  })
}

function removePayMethod(index: number) {
  payMethods.value.splice(index, 1)
}

async function savePayMethods() {
  const methods = payMethods.value
    .filter(m => m.label.trim())
    .map((m, i) => ({
      id:         m.id || ('pm_' + Date.now() + '_' + i),
      label:      m.label.trim(),
      enabled:    m.enabled,
      has_cash:   m.has_cash,
      sort_order: m.sort_order ?? i,
    }))

  if (!methods.length) { toast.show('至少需要一種付款方式', 'danger'); return }
  savingPay.value = true
  try {
    await http.put('/pos/payment-methods', { methods })
    // Write back generated IDs
    methods.forEach((m, i) => {
      if (!payMethods.value[i].id) payMethods.value[i].id = m.id
      payMethods.value[i]._isNew = false
    })
    toast.show('付款設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingPay.value = false
  }
}

async function saveLinePaySettings() {
  savingLinePay.value = true
  try {
    await http.put('/pos/linepay-settings', {
      enabled:        linePayEnabled.value,
      channel_id:     linePayChId.value,
      channel_secret: linePaySecret.value,
      sandbox:        linePaySandbox.value,
    })
    const [lpR, pmR2] = await Promise.all([
      http.get('/pos/linepay-settings'),
      http.get('/pos/payment-methods'),
    ])
    applyLinePay(lpR.data?.data || {})
    const pm2: PayMethod[] = pmR2.data?.data || []
    if (pm2.length) payMethods.value = pm2
    toast.show('LINE Pay 設定已儲存', 'success')
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    savingLinePay.value = false
  }
}

async function saveZPaySettings() {
  savingZPay.value = true
  try {
    await http.put('/pos/zpay-settings', {
      enabled:         zPayEnabled.value,
      merchant_id:     zPayMchId.value,
      merchant_secret: zPaySecret.value,
      sandbox:         zPaySandbox.value,
    })
    const [zpR, pmR2] = await Promise.all([
      http.get('/pos/zpay-settings'),
      http.get('/pos/payment-methods'),
    ])
    applyZPay(zpR.data?.data || {})
    const pm2: PayMethod[] = pmR2.data?.data || []
    if (pm2.length) payMethods.value = pm2
    toast.show('全支付設定已儲存', 'success')
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    savingZPay.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- ── POS 付款方式 ──────────────────────────────── -->
  <div class="col-12">
    <div class="table-card">
      <div class="table-header d-flex align-items-center justify-content-between">
        <h6><i class="bi bi-credit-card me-1 text-primary"></i>POS 付款方式</h6>
        <button class="btn btn-sm btn-outline-primary" @click="addPayMethodRow">
          <i class="bi bi-plus-lg me-1"></i>新增
        </button>
      </div>
      <div class="p-3">
        <div class="row g-1 mb-1 align-items-center fz-72" style="color:#6b7280">
          <div class="col-1 text-center">啟用</div>
          <div class="col-4">付款名稱</div>
          <div class="col-3 text-center">現金找零</div>
          <div class="col-2 text-center">排序</div>
          <div class="col-2"></div>
        </div>

        <div v-for="(m, i) in payMethods" :key="m.id || i" class="row g-1 mb-1 align-items-center">
          <div class="col-1 text-center">
            <input v-model="m.enabled" class="form-check-input" type="checkbox" />
          </div>
          <div class="col-4">
            <input
              v-model="m.label"
              type="text"
              class="form-control form-control-sm"
              placeholder="付款名稱"
              :readonly="m.id === 'cash'"
              :title="m.id === 'cash' ? '內建付款方式，名稱可改但不可刪除' : ''"
            />
          </div>
          <div class="col-3 text-center">
            <input v-model="m.has_cash" class="form-check-input" type="checkbox" />
          </div>
          <div class="col-2">
            <input
              v-model.number="m.sort_order"
              type="number"
              class="form-control form-control-sm"
              min="0"
            />
          </div>
          <div class="col-2 text-end">
            <span v-if="m.id === 'cash'" class="text-muted small" title="內建項目">—</span>
            <button
              v-else
              type="button"
              class="btn btn-sm btn-outline-danger py-0 px-1"
              @click="removePayMethod(i)"
             aria-label="移除" title="移除">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>

        <div class="form-text mb-3 mt-2">
          <b>現金找零</b>：勾選後 POS 顯示收現金額輸入欄與找零計算（現金類付款適用）。
          未勾選則為純標籤付款（刷卡、第三方支付等）。
        </div>
        <button class="btn btn-primary" :disabled="savingPay" @click="savePayMethods">
          <span v-if="savingPay" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-save me-1"></i>儲存付款設定
        </button>

        <hr class="mt-4 mb-3" />
        <div class="d-flex align-items-center justify-content-between mb-3">
          <div>
            <div class="fw-semibold"><i class="bi bi-wallet2 me-1 text-success"></i>LINE Pay 全支付</div>
            <small class="text-muted">啟用後付款方式自動加入 LINE Pay，收銀員掃描顧客條碼完成扣款</small>
          </div>
          <div class="form-check form-switch m-0">
            <input v-model="linePayEnabled" class="form-check-input switch-lg" type="checkbox" />
          </div>
        </div>
        <div v-if="linePayEnabled" class="row g-2 mb-3">
          <div class="col-12 col-md-4">
            <label class="form-label form-label-sm fw-semibold">Channel ID <span class="text-danger">*</span></label>
            <input v-model="linePayChId" type="text" class="form-control form-control-sm" placeholder="例：1234567890" />
          </div>
          <div class="col-12 col-md-5">
            <label class="form-label form-label-sm fw-semibold">Channel Secret <span class="text-danger">*</span></label>
            <input v-model="linePaySecret" type="password" class="form-control form-control-sm"
                   placeholder="已設定則顯示 ******" autocomplete="new-password" />
          </div>
          <div class="col-12 col-md-3 d-flex align-items-end">
            <div class="form-check form-switch m-0">
              <input v-model="linePaySandbox" class="form-check-input switch-md" type="checkbox"
                     id="lp-sandbox" />
              <label class="form-check-label small" for="lp-sandbox">Sandbox 測試模式</label>
            </div>
          </div>
        </div>
        <button class="btn btn-success" :disabled="savingLinePay" @click="saveLinePaySettings">
          <span v-if="savingLinePay" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-wallet2 me-1"></i>儲存 LINE Pay 設定
        </button>

        <hr class="mt-4 mb-3" />

        <!-- 全支付 -->
        <div class="d-flex align-items-center justify-content-between mb-3">
          <div>
            <div class="fw-semibold">
              <i class="bi bi-phone me-1 text-primary"></i>全支付
            </div>
            <small class="text-muted">啟用後付款方式自動加入「全支付」，收銀員掃描顧客全支付 App 條碼完成扣款</small>
          </div>
          <div class="form-check form-switch m-0">
            <input v-model="zPayEnabled" class="form-check-input switch-lg" type="checkbox" />
          </div>
        </div>
        <div v-if="zPayEnabled" class="row g-2 mb-3">
          <div class="col-12 col-md-4">
            <label class="form-label form-label-sm fw-semibold">Merchant ID <span class="text-danger">*</span></label>
            <input v-model="zPayMchId" type="text" class="form-control form-control-sm"
                   placeholder="全支付商家 ID" />
          </div>
          <div class="col-12 col-md-5">
            <label class="form-label form-label-sm fw-semibold">Merchant Secret <span class="text-danger">*</span></label>
            <input v-model="zPaySecret" type="password" class="form-control form-control-sm"
                   placeholder="已設定則顯示 ******" autocomplete="new-password" />
          </div>
          <div class="col-12 col-md-3 d-flex align-items-end">
            <div class="form-check form-switch m-0">
              <input v-model="zPaySandbox" class="form-check-input switch-md" type="checkbox"
                     id="zp-sandbox" />
              <label class="form-check-label small" for="zp-sandbox">Sandbox 測試模式</label>
            </div>
          </div>
        </div>
        <button class="btn btn-primary" :disabled="savingZPay" @click="saveZPaySettings">
          <span v-if="savingZPay" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-phone me-1"></i>儲存全支付設定
        </button>
      </div>
    </div>
  </div>
</template>
