<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

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

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [whR, settR, pmR, menR] = await Promise.all([
      http.get('/warehouse/'),
      http.get('/settings/'),
      http.get('/pos/payment-methods'),
      http.get('/menu/?status=1'),
    ])

    warehouses.value         = whR.data?.data || []
    menus.value              = menR.data?.data || []
    const s                  = settR.data?.data || {}
    defaultWarehouseId.value = s.default_warehouse_id || ''
    posDefaultMenuId.value   = s.pos_default_menu_id   || ''
    logRetentionDays.value   = Number(s.log_retention_days ?? 0)
    logLastCleanup.value     = s.log_last_cleanup_at   || null
    discountPresets.value    = s.pos_discount_presets  || []

    // payment methods — fallback to cash if empty
    const pm: PayMethod[] = pmR.data?.data || []
    payMethods.value = pm.length ? pm : [
      { id: 'cash', label: '現金', enabled: true, has_cash: true, sort_order: 0 }
    ]
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

  </div>
</template>
