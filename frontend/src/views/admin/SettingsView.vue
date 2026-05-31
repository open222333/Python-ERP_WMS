<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { useThemeStore, THEMES } from '@/stores/theme'

const toast = useToastStore()
const themeStore = useThemeStore()

// ── Types ────────────────────────────────────────────────
interface Warehouse { _id: string; name: string; code?: string }
interface PayMethod {
  id:         string
  label:      string
  enabled:    boolean
  has_cash:   boolean
  sort_order: number
  _isNew?:    boolean
}
interface DiscountPreset { label: string; type: 'percent' | 'fixed'; value: number }
interface Menu { _id: string; name: string }

// ── State ────────────────────────────────────────────────
const loading    = ref(false)
const saving     = ref(false)
const savingPay  = ref(false)
const savingDisc = ref(false)
const savingPos  = ref(false)
const savingLog  = ref(false)
const cleaningLog = ref(false)

const warehouses         = ref<Warehouse[]>([])
const menus              = ref<Menu[]>([])
const defaultWarehouseId = ref('')
const posDefaultMenuId   = ref('')
const logRetentionDays   = ref(0)
const logTotal           = ref<number | null>(null)
const logOlderCount      = ref<number | null>(null)
const logLastCleanup     = ref<string | null>(null)
const payMethods         = ref<PayMethod[]>([])
const discountPresets    = ref<DiscountPreset[]>([])

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

// ── 外觀主題 ─────────────────────────────────────────────
const adminTheme  = ref(themeStore.themeId)
const savingTheme = ref(false)
const customEdit  = ref({ ...themeStore.customColors.value })

function selectTheme(id: string) {
  adminTheme.value = id
  themeStore.applyTheme(id)
}

function onCustomColorChange() {
  themeStore.setCustomColors(customEdit.value)
  adminTheme.value = 'custom'
}

function setDark(v: boolean) {
  themeStore.applyDarkMode(v)
}

async function saveTheme() {
  savingTheme.value = true
  try {
    const payload: Record<string, string> = {
      admin_theme: adminTheme.value,
      admin_dark:  themeStore.darkMode ? '1' : '0',
    }
    if (adminTheme.value === 'custom') {
      payload.admin_custom_theme = JSON.stringify(themeStore.customColors.value)
    }
    await http.put('/settings/', payload)
    toast.show('外觀設定已儲存', 'success')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingTheme.value = false
  }
}

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [whR, settR, pmR, menR, lpR, zpR] = await Promise.all([
      http.get('/warehouse/'),
      http.get('/settings/'),
      http.get('/pos/payment-methods'),
      http.get('/menu/?status=1'),
      http.get('/pos/linepay-settings'),
      http.get('/pos/zpay-settings'),
    ])

    warehouses.value         = whR.data?.data || []
    menus.value              = menR.data?.data || []
    const s                  = settR.data?.data || {}
    defaultWarehouseId.value = s.default_warehouse_id || ''
    posDefaultMenuId.value   = s.pos_default_menu_id   || ''
    logRetentionDays.value   = Number(s.log_retention_days ?? 0)
    logLastCleanup.value     = s.log_last_cleanup_at   || null
    discountPresets.value    = s.pos_discount_presets  || []
    if (s.admin_theme) {
      adminTheme.value = s.admin_theme
      themeStore.applyTheme(s.admin_theme)
    }
    if (s.admin_dark !== undefined) {
      themeStore.applyDarkMode(s.admin_dark === '1')
    }
    if (s.admin_custom_theme) {
      try {
        const colors = JSON.parse(s.admin_custom_theme)
        themeStore.setCustomColors(colors)
        customEdit.value = { ...colors }
      } catch {}
    }

    // payment methods — fallback to cash if empty
    const pm: PayMethod[] = pmR.data?.data || []
    payMethods.value = pm.length ? pm : [
      { id: 'cash', label: '現金', enabled: true, has_cash: true, sort_order: 0 }
    ]

    const lp = lpR.data?.data || {}
    linePayEnabled.value = !!lp.enabled
    linePayChId.value    = lp.channel_id || ''
    linePaySecret.value  = lp.channel_secret || ''
    linePaySandbox.value = lp.sandbox ?? true

    const zp = zpR.data?.data || {}
    zPayEnabled.value = !!zp.enabled
    zPayMchId.value   = zp.merchant_id || ''
    zPaySecret.value  = zp.merchant_secret || ''
    zPaySandbox.value = zp.sandbox ?? true
  } catch {
    toast.show('載入設定失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Save warehouse + POS default menu ────────────────────
async function saveSettings() {
  saving.value = true
  try {
    await http.put('/settings/', {
      default_warehouse_id: defaultWarehouseId.value || null,
    })
    toast.show('倉庫設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function savePosSettings() {
  savingPos.value = true
  try {
    await http.put('/settings/', {
      pos_default_menu_id: posDefaultMenuId.value || null,
    })
    toast.show('POS 設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingPos.value = false
  }
}

// ── Pay Methods ───────────────────────────────────────────
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
    const lp = lpR.data?.data || {}
    linePayEnabled.value = !!lp.enabled
    linePayChId.value    = lp.channel_id || ''
    linePaySecret.value  = lp.channel_secret || ''
    linePaySandbox.value = lp.sandbox ?? true
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
    const zp = zpR.data?.data || {}
    zPayEnabled.value = !!zp.enabled
    zPayMchId.value   = zp.merchant_id || ''
    zPaySecret.value  = zp.merchant_secret || ''
    zPaySandbox.value = zp.sandbox ?? true
    const pm2: PayMethod[] = pmR2.data?.data || []
    if (pm2.length) payMethods.value = pm2
    toast.show('全支付設定已儲存', 'success')
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    savingZPay.value = false
  }
}

// ── Discount Presets ──────────────────────────────────────
function addDiscountRow() {
  discountPresets.value.push({ label: '', type: 'percent', value: 0 })
}

function removeDiscountRow(index: number) {
  discountPresets.value.splice(index, 1)
}

async function saveDiscountPresets() {
  const presets = discountPresets.value
    .filter(p => p.label.trim() && !isNaN(p.value) && (p.type === 'percent' ? p.value >= 0 : p.value > 0))
    .map(p => ({ label: p.label.trim(), type: p.type, value: Number(p.value) }))

  savingDisc.value = true
  try {
    await http.put('/settings/', { pos_discount_presets: presets })
    discountPresets.value = presets
    toast.show('折扣設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingDisc.value = false
  }
}

// ── Log stats ─────────────────────────────────────────────
async function loadLogStats() {
  try {
    const { data } = await http.get('/log/stats')
    logTotal.value      = data.total      ?? null
    logOlderCount.value = data.older_count ?? null
    logLastCleanup.value = data.last_cleanup ?? null
  } catch {
    /* 非致命，靜默 */
  }
}

async function saveLogSettings() {
  savingLog.value = true
  try {
    await http.put('/settings/', { log_retention_days: logRetentionDays.value })
    toast.show('操作紀錄保留設定已儲存')
    await loadLogStats()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingLog.value = false
  }
}

async function cleanupLogs() {
  if (!logRetentionDays.value) {
    toast.show('請先設定保留天數', 'danger')
    return
  }
  if (!confirm(`確認清除 ${logRetentionDays.value} 天前的操作紀錄？此操作無法復原。`)) return
  cleaningLog.value = true
  try {
    const { data } = await http.post('/log/cleanup', { days: logRetentionDays.value })
    toast.show(`已清除 ${data.deleted} 筆超齡紀錄`, 'success')
    await loadLogStats()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '清除失敗', 'danger')
  } finally {
    cleaningLog.value = false
  }
}

function fmtCleanup(iso: string | null) {
  if (!iso) return '從未清除'
  return new Date(iso).toLocaleString('zh-TW', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

onMounted(async () => {
  await load()
  await loadLogStats()
})
</script>

<template>
  <div class="row g-4">

    <!-- ── 倉庫設定 ───────────────────────────────────── -->
    <div class="col-12 col-xl-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-building me-1 text-primary"></i>倉庫設定</h6>
        </div>
        <div class="p-4">
          <div class="mb-4">
            <label class="form-label fw-semibold">預設倉庫</label>
            <select v-model="defaultWarehouseId" class="form-select">
              <option value="">— 不指定預設倉庫 —</option>
              <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
            </select>
            <div class="form-text mt-2">
              <span class="badge bg-primary me-1">POS 收銀台</span>
              <span class="badge bg-warning text-dark me-1">快速出入庫</span>
              開啟時自動選取此倉庫，減少每次手動選擇。
            </div>
          </div>
          <button class="btn btn-primary" :disabled="saving" @click="saveSettings">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-save me-1"></i>儲存設定
          </button>
        </div>
      </div>
    </div>

    <!-- ── POS 預設菜單 ──────────────────────────────── -->
    <div class="col-12 col-xl-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-menu-button-wide me-1 text-primary"></i>POS 收銀台設定</h6>
        </div>
        <div class="p-4">
          <div class="mb-4">
            <label class="form-label fw-semibold">預設菜單</label>
            <select v-model="posDefaultMenuId" class="form-select">
              <option value="">— 不指定預設菜單（顯示全部商品）—</option>
              <option v-for="m in menus" :key="m._id" :value="m._id">{{ m.name }}</option>
            </select>
            <div class="form-text mt-2">
              <span class="badge bg-primary me-1">POS 收銀台</span>
              開啟時自動切換至此菜單，仍可手動切換至其他菜單或商品模式。
            </div>
          </div>
          <button class="btn btn-primary" :disabled="savingPos" @click="savePosSettings">
            <span v-if="savingPos" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-save me-1"></i>儲存設定
          </button>
        </div>
      </div>
    </div>

    <!-- ── 設定用途說明 ──────────────────────────────── -->
    <div class="col-12 col-xl-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-info-circle me-1 text-info"></i>設定用途說明</h6>
        </div>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead class="table-light">
              <tr><th>設定項目</th><th>功能</th><th>說明</th></tr>
            </thead>
            <tbody>
              <tr>
                <td class="fw-semibold text-nowrap">預設倉庫</td>
                <td>
                  <span class="badge bg-primary me-1">POS 收銀台</span>
                  <span class="badge bg-warning text-dark">快速出入庫</span>
                </td>
                <td class="text-muted small">開啟頁面後自動選取此倉庫，仍可手動切換</td>
              </tr>
              <tr>
                <td class="fw-semibold text-nowrap">POS 預設菜單</td>
                <td><span class="badge bg-primary">POS 收銀台</span></td>
                <td class="text-muted small">開啟 POS 後自動切換至指定菜單，方便快速點餐</td>
              </tr>
              <tr>
                <td class="fw-semibold text-nowrap">使用者模板</td>
                <td><span class="badge bg-secondary">使用者管理</span></td>
                <td class="text-muted small">在「使用者管理 → 使用者模板」Tab 設定，決定帳號的系統角色與登入後的側欄頁面顯示</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── POS 折扣快捷 ──────────────────────────────── -->
    <div class="col-12">
      <div class="table-card">
        <div class="table-header d-flex align-items-center justify-content-between">
          <h6><i class="bi bi-percent me-1 text-primary"></i>POS 折扣快捷</h6>
          <button class="btn btn-sm btn-outline-primary" @click="addDiscountRow">
            <i class="bi bi-plus-lg me-1"></i>新增
          </button>
        </div>
        <div class="p-3">
          <div class="row g-1 mb-2 align-items-center" style="font-size: .72rem; color: #6b7280">
            <div class="col-3">顯示名稱</div>
            <div class="col-5">類型</div>
            <div class="col-2 text-end">數值</div>
            <div class="col-2"></div>
          </div>
          <div v-for="(p, i) in discountPresets" :key="i" class="row g-1 mb-1 align-items-center">
            <div class="col-3">
              <input
                v-model="p.label"
                type="text"
                class="form-control form-control-sm"
                placeholder="名稱"
              />
            </div>
            <div class="col-5">
              <select v-model="p.type" class="form-select form-select-sm">
                <option value="percent">折扣%（如 90 = 九折）</option>
                <option value="fixed">固定折抵（元）</option>
              </select>
            </div>
            <div class="col-2">
              <input
                v-model.number="p.value"
                type="number"
                class="form-control form-control-sm text-end"
                min="0"
                placeholder="數值"
              />
            </div>
            <div class="col-2 text-end">
              <button
                type="button"
                class="btn btn-sm btn-outline-danger py-0 px-1"
                @click="removeDiscountRow(i)"
              >
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
          </div>
          <div class="form-text mb-3 mt-2">
            <b>折扣%</b>：輸入數字，例如 90 = 九折（小計 × 0.9）。填 <b>0</b> = 免費贈送（全額折抵）。<br />
            <b>固定折抵</b>：輸入折抵金額，例如 50 = 折抵 $50。
          </div>
          <button class="btn btn-primary" :disabled="savingDisc" @click="saveDiscountPresets">
            <span v-if="savingDisc" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-save me-1"></i>儲存折扣設定
          </button>
        </div>
      </div>
    </div>

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
          <div class="row g-1 mb-1 align-items-center" style="font-size: .72rem; color: #6b7280">
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
              >
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
              <input v-model="linePayEnabled" class="form-check-input" type="checkbox"
                     style="width:2.5em;height:1.3em;cursor:pointer" />
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
                <input v-model="linePaySandbox" class="form-check-input" type="checkbox"
                       id="lp-sandbox" style="width:2.2em;height:1.2em;cursor:pointer" />
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
              <input v-model="zPayEnabled" class="form-check-input" type="checkbox"
                     style="width:2.5em;height:1.3em;cursor:pointer" />
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
                <input v-model="zPaySandbox" class="form-check-input" type="checkbox"
                       id="zp-sandbox" style="width:2.2em;height:1.2em;cursor:pointer" />
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

    <!-- ── 操作紀錄保留設定 ──────────────────────── -->
    <div class="col-12">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-journal-text me-1 text-primary"></i>操作紀錄管理</h6>
        </div>
        <div class="p-4">
          <div class="row g-3 align-items-end">

            <!-- 保留天數設定 -->
            <div class="col-12 col-md-4">
              <label class="form-label fw-semibold">自動清除保留天數</label>
              <select v-model.number="logRetentionDays" class="form-select">
                <option :value="0">不自動清除</option>
                <option :value="30">30 天</option>
                <option :value="60">60 天</option>
                <option :value="90">90 天</option>
                <option :value="180">180 天</option>
                <option :value="365">365 天（1 年）</option>
              </select>
              <div class="form-text">
                系統每天在查看操作紀錄時自動清除超齡資料。
                設為「不自動清除」則僅能手動清除。
              </div>
            </div>

            <!-- 統計資訊 -->
            <div class="col-12 col-md-4">
              <div class="p-3 bg-light rounded border">
                <div class="small text-muted mb-1">紀錄統計</div>
                <div class="d-flex justify-content-between">
                  <span class="text-muted small">總筆數：</span>
                  <strong>{{ logTotal !== null ? logTotal.toLocaleString() : '—' }}</strong>
                </div>
                <div v-if="logRetentionDays > 0" class="d-flex justify-content-between mt-1">
                  <span class="text-muted small">超過 {{ logRetentionDays }} 天：</span>
                  <strong :class="(logOlderCount ?? 0) > 0 ? 'text-danger' : ''">
                    {{ logOlderCount !== null ? logOlderCount.toLocaleString() : '—' }} 筆
                  </strong>
                </div>
                <div class="d-flex justify-content-between mt-1">
                  <span class="text-muted small">上次清除：</span>
                  <span class="small">{{ fmtCleanup(logLastCleanup) }}</span>
                </div>
              </div>
            </div>

            <!-- 操作按鈕 -->
            <div class="col-12 col-md-4 d-flex flex-column gap-2">
              <button
                class="btn btn-primary"
                :disabled="savingLog"
                @click="saveLogSettings"
              >
                <span v-if="savingLog" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-save me-1"></i>儲存保留設定
              </button>
              <button
                class="btn btn-outline-danger"
                :disabled="cleaningLog || !logRetentionDays"
                @click="cleanupLogs"
                :title="logRetentionDays ? `立即刪除 ${logRetentionDays} 天前的紀錄` : '請先設定保留天數'"
              >
                <span v-if="cleaningLog" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-trash3 me-1"></i>立即清除超齡紀錄
                <span v-if="logRetentionDays && logOlderCount" class="badge bg-danger ms-1">
                  {{ logOlderCount }}
                </span>
              </button>
            </div>

          </div>
        </div>
      </div>
    </div>

    <!-- ── 後台外觀配色 ──────────────────────────────── -->
    <div class="col-12">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-palette me-1 text-primary"></i>後台外觀配色</h6>
        </div>
        <div class="p-4">

          <!-- 深淺色模式 -->
          <div class="mb-4">
            <div class="fw-semibold small mb-2">色調模式</div>
            <div class="d-flex gap-2">
              <button
                class="btn btn-sm d-flex align-items-center gap-1"
                :class="!themeStore.darkMode ? 'btn-primary' : 'btn-outline-secondary'"
                @click="setDark(false)"
              >
                <i class="bi bi-sun-fill"></i>淺色
              </button>
              <button
                class="btn btn-sm d-flex align-items-center gap-1"
                :class="themeStore.darkMode ? 'btn-primary' : 'btn-outline-secondary'"
                @click="setDark(true)"
              >
                <i class="bi bi-moon-stars-fill"></i>深色
              </button>
            </div>
          </div>

          <!-- 側欄主題 -->
          <div class="fw-semibold small mb-2">側欄主題</div>
          <p class="text-muted small mb-3">點擊即時預覽，儲存後下次開啟自動套用。</p>
          <div class="theme-grid mb-3">
            <!-- 預設主題 -->
            <div
              v-for="t in THEMES" :key="t.id"
              class="theme-card"
              :class="{ active: adminTheme === t.id }"
              @click="selectTheme(t.id)"
            >
              <div class="theme-preview" :style="{ background: t.sidebarBg }">
                <div class="tp-row">
                  <div class="tp-dot" :style="{ background: t.accent }"></div>
                  <div class="tp-line" :style="{ background: t.accent, opacity: .9 }"></div>
                </div>
                <div class="tp-row" style="opacity:.3">
                  <div class="tp-dot"></div>
                  <div class="tp-line"></div>
                </div>
                <div class="tp-row" style="opacity:.2">
                  <div class="tp-dot"></div>
                  <div class="tp-line"></div>
                </div>
                <div class="tp-accent-bar" :style="{ background: t.accent }"></div>
                <div v-if="adminTheme === t.id" class="tp-check">
                  <i class="bi bi-check-lg"></i>
                </div>
              </div>
              <div class="theme-label">{{ t.name }}</div>
            </div>

            <!-- 自訂主題 -->
            <div
              class="theme-card"
              :class="{ active: adminTheme === 'custom' }"
              @click="selectTheme('custom')"
            >
              <div class="theme-preview" :style="{ background: customEdit.sidebarBg }">
                <div class="tp-row">
                  <div class="tp-dot" :style="{ background: customEdit.accent }"></div>
                  <div class="tp-line" :style="{ background: customEdit.accent, opacity: .9 }"></div>
                </div>
                <div class="tp-row" style="opacity:.3">
                  <div class="tp-dot"></div>
                  <div class="tp-line"></div>
                </div>
                <div class="tp-row" style="opacity:.2">
                  <div class="tp-dot"></div>
                  <div class="tp-line"></div>
                </div>
                <div class="tp-accent-bar" :style="{ background: customEdit.accent }"></div>
                <div v-if="adminTheme === 'custom'" class="tp-check">
                  <i class="bi bi-check-lg"></i>
                </div>
                <div v-else class="tp-edit-icon"><i class="bi bi-pencil-fill"></i></div>
              </div>
              <div class="theme-label">自訂</div>
            </div>
          </div>

          <!-- 自訂主題顏色選擇器 -->
          <div v-if="adminTheme === 'custom'" class="custom-color-editor mb-4">
            <div class="fw-semibold small mb-2">自訂側欄顏色</div>
            <div class="d-flex flex-wrap gap-3">
              <div class="color-pick-item">
                <label class="form-label form-label-sm mb-1">側欄底色</label>
                <div class="d-flex align-items-center gap-2">
                  <input
                    v-model="customEdit.sidebarBg"
                    type="color"
                    class="form-control form-control-color"
                    @input="onCustomColorChange"
                  />
                  <input
                    v-model="customEdit.sidebarBg"
                    type="text"
                    class="form-control form-control-sm color-hex"
                    maxlength="7"
                    placeholder="#1a1d2e"
                    @change="onCustomColorChange"
                  />
                </div>
              </div>
              <div class="color-pick-item">
                <label class="form-label form-label-sm mb-1">側欄 Hover</label>
                <div class="d-flex align-items-center gap-2">
                  <input
                    v-model="customEdit.sidebarHover"
                    type="color"
                    class="form-control form-control-color"
                    @input="onCustomColorChange"
                  />
                  <input
                    v-model="customEdit.sidebarHover"
                    type="text"
                    class="form-control form-control-sm color-hex"
                    maxlength="7"
                    placeholder="#2d3250"
                    @change="onCustomColorChange"
                  />
                </div>
              </div>
              <div class="color-pick-item">
                <label class="form-label form-label-sm mb-1">強調色</label>
                <div class="d-flex align-items-center gap-2">
                  <input
                    v-model="customEdit.accent"
                    type="color"
                    class="form-control form-control-color"
                    @input="onCustomColorChange"
                  />
                  <input
                    v-model="customEdit.accent"
                    type="text"
                    class="form-control form-control-sm color-hex"
                    maxlength="7"
                    placeholder="#5c7cfa"
                    @change="onCustomColorChange"
                  />
                </div>
              </div>
            </div>
          </div>

          <button class="btn btn-primary" :disabled="savingTheme" @click="saveTheme">
            <span v-if="savingTheme" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-palette me-1"></i>儲存外觀設定
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* ── 主題選擇器 ── */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
@media (max-width: 768px) { .theme-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .theme-grid { grid-template-columns: repeat(2, 1fr); } }

.theme-card {
  cursor: pointer;
  border-radius: 10px;
  border: 2.5px solid #e2e8f0;
  overflow: hidden;
  transition: border-color .15s, transform .12s, box-shadow .15s;
  box-shadow: 0 1px 4px rgba(0,0,0,.07);
  user-select: none;
}
.theme-card:hover  { border-color: #94a3b8; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.12); }
.theme-card.active { border-color: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.2); }

.theme-preview {
  height: 72px;
  padding: 10px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}
.tp-row  { display: flex; align-items: center; gap: 5px; }
.tp-dot  { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,.25); flex-shrink: 0; }
.tp-line { height: 5px; flex: 1; border-radius: 3px; background: rgba(255,255,255,.25); }

.tp-accent-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 8px;
}
.tp-check {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -55%);
  width: 26px; height: 26px;
  background: rgba(255,255,255,.92);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #16a34a; font-size: .95rem; font-weight: 800;
}

.theme-label {
  padding: 7px 8px;
  font-size: .77rem;
  font-weight: 600;
  text-align: center;
  background: var(--card-bg, #fff);
  color: var(--text-main, #374151);
}

.tp-edit-icon {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -55%);
  width: 26px; height: 26px;
  background: rgba(255,255,255,.2);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: .8rem;
}

/* Custom color editor */
.custom-color-editor {
  background: var(--table-th-bg, #f8f9fa);
  border: 1px solid var(--card-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
}
.color-pick-item { min-width: 180px; }
.color-hex { width: 90px; font-family: monospace; font-size: .8rem; }
.form-control-color { width: 40px; height: 34px; padding: 2px; cursor: pointer; }
</style>
