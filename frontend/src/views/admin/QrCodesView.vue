<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import QRCode from 'qrcode'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

// ── 型別 ────────────────────────────────────────────────
interface TableEntry {
  table_no:   string
  label:      string
  enabled:    boolean
  token:      string
  expires_at: string
}

// ── State ────────────────────────────────────────────────
const baseUrl     = ref(window.location.origin)
const entries     = ref<TableEntry[]>([])
const qrUrls      = ref<Record<string, string>>({})
const loading     = ref(false)
const saving      = ref(false)
const refreshing  = ref(false)

// Token 設定
const ttlHours     = ref(24)
const lastRefresh  = ref('')

// 單筆新增
const newTableNo = ref('')
const newLabel   = ref('')

// 批次生成
const batchPrefix   = ref('')
const batchFrom     = ref(1)
const batchTo       = ref(5)
const batchLabelTpl = ref('{n}')

// ── 工具 ────────────────────────────────────────────────
function orderUrl(token: string) {
  return `${baseUrl.value}/order/?t=${encodeURIComponent(token)}`
}

async function genQR(token: string) {
  qrUrls.value[token] = await QRCode.toDataURL(orderUrl(token), {
    width: 120, margin: 1,
    color: { dark: '#000000', light: '#ffffff' },
  })
}

async function genAll() {
  for (const e of entries.value) {
    if (e.token) await genQR(e.token)
  }
}

function isExpired(e: TableEntry) {
  if (!e.expires_at) return false
  return new Date(e.expires_at) < new Date()
}

function fmtExpiry(isoStr: string) {
  if (!isoStr) return '--'
  const d = new Date(isoStr)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function nextRefreshStr() {
  if (!lastRefresh.value) return '--'
  const next = new Date(new Date(lastRefresh.value).getTime() + ttlHours.value * 3600 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${next.getFullYear()}-${pad(next.getMonth()+1)}-${pad(next.getDate())} ${pad(next.getHours())}:${pad(next.getMinutes())}`
}

// ── 載入 ────────────────────────────────────────────────
async function loadTokens() {
  loading.value = true
  try {
    const res = await http.get('/customer-order/tokens')
    const d = res.data.data
    ttlHours.value    = d.ttl_hours || 24
    lastRefresh.value = d.last_refresh || ''
    const tokens: Record<string, any> = d.tokens || {}
    entries.value = Object.entries(tokens).map(([table_no, info]) => ({
      table_no,
      label:      info.label || table_no,
      enabled:    info.enabled !== false,
      token:      info.token || '',
      expires_at: info.expires_at || '',
    }))
    await genAll()
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── 儲存桌位清單 ─────────────────────────────────────────
async function saveTables() {
  saving.value = true
  try {
    const res = await http.put('/customer-order/tokens/tables', {
      tables: entries.value.map(e => ({
        table_no: e.table_no,
        label:    e.label,
        enabled:  e.enabled,
      })),
    })
    const newData: Record<string, any> = res.data.data || {}
    // 更新 token（新桌位才有新 token）
    entries.value = entries.value.map(e => {
      const updated = newData[e.table_no]
      if (updated && updated.token !== e.token) {
        genQR(updated.token)
        return { ...e, token: updated.token, expires_at: updated.expires_at }
      }
      return e
    })
    toast.show('儲存成功', 'success')
  } catch {
    toast.show('儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

// ── 刷新所有 Token ───────────────────────────────────────
async function refreshAllTokens() {
  if (!confirm(`確定要刷新所有桌位的 QR Token 嗎？\n刷新後舊 QR Code 立即失效，需重新列印。`)) return
  refreshing.value = true
  try {
    const res = await http.post('/customer-order/tokens/refresh', {
      ttl_hours: ttlHours.value,
    })
    const d = res.data.data
    lastRefresh.value = d.last_refresh || ''
    const newTokens: Record<string, any> = d.tokens || {}
    entries.value = entries.value.map(e => {
      const info = newTokens[e.table_no]
      if (!info) return e
      genQR(info.token)
      return { ...e, token: info.token, expires_at: info.expires_at }
    })
    toast.show('已刷新所有 Token', 'success')
  } catch {
    toast.show('刷新失敗', 'danger')
  } finally {
    refreshing.value = false
  }
}

// ── 新增桌位 ─────────────────────────────────────────────
async function addSingle() {
  const table_no = newTableNo.value.trim()
  if (!table_no) return
  if (entries.value.some(e => e.table_no === table_no)) {
    toast.show('桌號已存在', 'warning'); return
  }
  entries.value.push({
    table_no, label: newLabel.value.trim() || table_no,
    enabled: true, token: '', expires_at: '',
  })
  newTableNo.value = ''
  newLabel.value   = ''
  await saveTables()
}

async function batchGenerate() {
  const prefix = batchPrefix.value.trim()
  const from = Number(batchFrom.value)
  const to   = Number(batchTo.value)
  if (from > to || to - from > 99) return
  let added = false
  for (let n = from; n <= to; n++) {
    const table_no = `${prefix}${n}`
    if (entries.value.some(e => e.table_no === table_no)) continue
    const label = batchLabelTpl.value.replace('{n}', table_no)
    entries.value.push({ table_no, label, enabled: true, token: '', expires_at: '' })
    added = true
  }
  if (added) await saveTables()
}

// ── 刪除 ─────────────────────────────────────────────────
async function remove(table_no: string) {
  entries.value = entries.value.filter(e => e.table_no !== table_no)
  delete qrUrls.value[entries.find(e => e.table_no === table_no)?.token || '']
  await saveTables()
}

// ── 開關 ─────────────────────────────────────────────────
async function toggleEnabled(e: TableEntry) {
  e.enabled = !e.enabled
  await saveTables()
}

// ── 下載 / 複製 / 列印 ───────────────────────────────────
function download(e: TableEntry) {
  const url = qrUrls.value[e.token]
  if (!url) return
  const a = document.createElement('a')
  a.download = `qr-${e.table_no}.png`
  a.href = url
  a.click()
}

function copyUrl(e: TableEntry) {
  navigator.clipboard.writeText(orderUrl(e.token))
  toast.show('已複製網址', 'success')
}

function printAll() { window.print() }

// ── 統計 ────────────────────────────────────────────────
const enabledCount  = computed(() => entries.value.filter(e => e.enabled).length)
const expiredCount  = computed(() => entries.value.filter(e => isExpired(e)).length)

onMounted(loadTokens)
</script>

<template>
  <div class="container-fluid py-3 px-4">

    <!-- ── 標題列 ─────────────────────────────────────── -->
    <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
      <div>
        <h5 class="mb-0 fw-bold">
          <i class="bi bi-qr-code me-2 text-primary"></i>顧客點餐 QR 碼管理
        </h5>
        <small v-if="entries.length" class="text-muted">
          共 {{ entries.length }} 桌・啟用 {{ enabledCount }}
          <span v-if="expiredCount" class="text-danger ms-2">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>{{ expiredCount }} 個已過期
          </span>
        </small>
      </div>
      <div class="d-flex gap-2 no-print">
        <button class="btn btn-outline-secondary btn-sm" @click="printAll">
          <i class="bi bi-printer me-1"></i>列印全部
        </button>
      </div>
    </div>

    <!-- ── Token 設定卡 ──────────────────────────────── -->
    <div class="card mb-3 shadow-sm no-print border-primary border-opacity-25">
      <div class="card-header py-2 fw-semibold small bg-primary bg-opacity-10">
        <i class="bi bi-key me-1 text-primary"></i>Token 時效設定
      </div>
      <div class="card-body py-2">
        <div class="row g-2 align-items-end">
          <div class="col-auto">
            <label class="form-label form-label-sm mb-1">有效時數（TTL）</label>
            <div class="input-group input-group-sm" style="width:180px">
              <input v-model.number="ttlHours" type="number" min="1" max="8760"
                     class="form-control" />
              <span class="input-group-text">小時</span>
            </div>
          </div>
          <div class="col-auto">
            <button class="btn btn-warning btn-sm fw-semibold"
                    @click="refreshAllTokens" :disabled="refreshing || !entries.length">
              <span v-if="refreshing" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-arrow-repeat me-1"></i>
              立即刷新所有 Token
            </button>
          </div>
          <div class="col-12 col-md-auto ms-md-auto">
            <div class="text-muted small lh-sm">
              <div>上次刷新：<strong>{{ lastRefresh ? fmtExpiry(lastRefresh) : '未刷新' }}</strong></div>
              <div>下次自動刷新（約）：<strong>{{ nextRefreshStr() }}</strong></div>
            </div>
          </div>
        </div>
        <div class="alert alert-warning py-1 px-2 mt-2 mb-0 small">
          <i class="bi bi-exclamation-triangle me-1"></i>
          刷新後所有舊 QR Code 立即失效，請重新列印桌卡後才能讓顧客使用。
        </div>
      </div>
    </div>

    <!-- ── 網址前綴 ───────────────────────────────────── -->
    <div class="card mb-3 shadow-sm no-print">
      <div class="card-header py-2 fw-semibold small">
        <i class="bi bi-link-45deg me-1"></i>點餐頁網址設定
      </div>
      <div class="card-body py-2">
        <div class="input-group input-group-sm" style="max-width:480px">
          <span class="input-group-text">前綴</span>
          <input v-model="baseUrl" type="url" class="form-control" @change="genAll"
                 placeholder="https://your-domain.com" />
        </div>
        <div class="form-text mt-1">
          QR 碼連結格式：<code>{{ baseUrl }}/order/?t=TOKEN</code>（Token 由系統產生，顧客無法猜測）
        </div>
      </div>
    </div>

    <!-- ── 新增區 ─────────────────────────────────────── -->
    <div class="row g-3 mb-3 no-print">
      <div class="col-12 col-lg-6">
        <div class="card shadow-sm h-100">
          <div class="card-header py-2 fw-semibold small">
            <i class="bi bi-plus-circle me-1"></i>單筆新增
          </div>
          <div class="card-body py-2">
            <div class="row g-2">
              <div class="col-4">
                <label class="form-label form-label-sm mb-1">桌號 <span class="text-danger">*</span></label>
                <input v-model="newTableNo" type="text" class="form-control form-control-sm"
                       placeholder="A1" @keyup.enter="addSingle" />
              </div>
              <div class="col-5">
                <label class="form-label form-label-sm mb-1">標籤（選填）</label>
                <input v-model="newLabel" type="text" class="form-control form-control-sm"
                       placeholder="A 區 1 號桌" @keyup.enter="addSingle" />
              </div>
              <div class="col-3 d-flex align-items-end">
                <button class="btn btn-primary btn-sm w-100" @click="addSingle"
                        :disabled="!newTableNo.trim() || saving">
                  <i class="bi bi-plus-lg me-1"></i>新增
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col-12 col-lg-6">
        <div class="card shadow-sm h-100">
          <div class="card-header py-2 fw-semibold small">
            <i class="bi bi-lightning-charge me-1"></i>批次自動生成
          </div>
          <div class="card-body py-2">
            <div class="row g-2">
              <div class="col-3">
                <label class="form-label form-label-sm mb-1">前綴</label>
                <input v-model="batchPrefix" type="text" class="form-control form-control-sm"
                       placeholder="A" maxlength="10" />
              </div>
              <div class="col-2">
                <label class="form-label form-label-sm mb-1">從</label>
                <input v-model.number="batchFrom" type="number" min="1"
                       class="form-control form-control-sm" />
              </div>
              <div class="col-2">
                <label class="form-label form-label-sm mb-1">到</label>
                <input v-model.number="batchTo" type="number" min="1"
                       class="form-control form-control-sm" />
              </div>
              <div class="col-3">
                <label class="form-label form-label-sm mb-1">標籤模板</label>
                <input v-model="batchLabelTpl" type="text" class="form-control form-control-sm"
                       placeholder="{n}" />
              </div>
              <div class="col-2 d-flex align-items-end">
                <button class="btn btn-success btn-sm w-100" @click="batchGenerate"
                        :disabled="batchFrom > batchTo || batchTo - batchFrom > 99 || saving">
                  生成
                </button>
              </div>
            </div>
            <div class="form-text mt-1">例：前綴「A」1 到 5，標籤「{n} 號桌」→ A1～A5</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 空狀態 ─────────────────────────────────────── -->
    <div v-if="loading" class="text-center text-muted py-5">
      <div class="spinner-border spinner-border-sm me-2"></div>載入中...
    </div>
    <div v-else-if="!entries.length" class="text-center text-muted py-5">
      <i class="bi bi-qr-code-scan" style="font-size:3rem;opacity:.3"></i>
      <p class="mt-2 mb-0">尚未新增任何桌位 QR 碼</p>
    </div>

    <!-- ── 列表 ───────────────────────────────────────── -->
    <div v-else class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light no-print">
            <tr>
              <th style="width:110px">QR 圖片</th>
              <th>桌號 / 標籤</th>
              <th class="d-none d-md-table-cell">Token 狀態</th>
              <th class="text-center no-print" style="width:70px">啟用</th>
              <th class="text-center no-print" style="width:130px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in entries" :key="e.table_no"
                :class="{ 'table-secondary text-muted': !e.enabled }">

              <!-- QR 圖片 -->
              <td class="py-2">
                <img v-if="e.token && qrUrls[e.token]"
                     :src="qrUrls[e.token]"
                     :alt="`QR ${e.table_no}`"
                     :style="{ width: '90px', opacity: e.enabled && !isExpired(e) ? 1 : 0.3 }"
                     class="qr-img rounded" />
                <div v-else class="text-muted small">生成中...</div>
              </td>

              <!-- 桌號 / 標籤 -->
              <td>
                <div class="fw-semibold">{{ e.label }}</div>
                <small class="text-muted font-monospace">{{ e.table_no }}</small>
              </td>

              <!-- Token 狀態 -->
              <td class="d-none d-md-table-cell">
                <div v-if="isExpired(e)" class="text-danger small fw-semibold">
                  <i class="bi bi-exclamation-triangle-fill me-1"></i>已過期
                </div>
                <div v-else class="text-success small">
                  <i class="bi bi-check-circle-fill me-1"></i>有效
                </div>
                <div class="text-muted" style="font-size:.75rem">
                  到期：{{ fmtExpiry(e.expires_at) }}
                </div>
                <div class="d-flex align-items-center gap-1 no-print mt-1">
                  <code class="small text-truncate" style="max-width:200px">
                    {{ orderUrl(e.token) }}
                  </code>
                  <button class="btn btn-link btn-sm p-0 text-muted" @click="copyUrl(e)"
                          title="複製點餐連結">
                    <i class="bi bi-clipboard"></i>
                  </button>
                </div>
                <!-- 列印時顯示文字 -->
                <span class="print-only small">{{ orderUrl(e.token) }}</span>
              </td>

              <!-- 開關 -->
              <td class="text-center no-print">
                <div class="form-check form-switch d-inline-block m-0">
                  <input class="form-check-input" type="checkbox"
                         :checked="e.enabled" @change="toggleEnabled(e)"
                         style="cursor:pointer;width:2.2em;height:1.2em" />
                </div>
              </td>

              <!-- 操作 -->
              <td class="text-center no-print">
                <button class="btn btn-sm btn-outline-secondary me-1" @click="download(e)"
                        title="下載 PNG" :disabled="!e.token || !qrUrls[e.token]">
                  <i class="bi bi-download"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" @click="remove(e.table_no)"
                        title="刪除" :disabled="saving">
                  <i class="bi bi-trash3"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>

<style scoped>
.qr-img { display: block; }

@media print {
  .no-print   { display: none !important; }
  .print-only { display: block !important; }
  th, td      { font-size: .8rem !important; }
  tr          { break-inside: avoid; }
  .qr-img     { width: 80px !important; opacity: 1 !important; }
}
@media screen {
  .print-only { display: none; }
}
</style>
