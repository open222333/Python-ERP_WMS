<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import QRCode from 'qrcode'

// ── 型別 ────────────────────────────────────────────────
interface Entry {
  id:       number
  name:     string    // 識別碼（URL 參數）
  label:    string    // 標籤（顯示名稱）
  enabled:  boolean
}

interface EditState {
  name:  string
  label: string
}

const STORAGE_KEY = 'wms-qr-tables'
let   uid = Date.now()

// ── State ────────────────────────────────────────────────
const baseUrl   = ref(window.location.origin)
const entries   = ref<Entry[]>([])
const qrUrls    = ref<Record<number, string>>({})
const editMap   = ref<Record<number, EditState>>({})   // 正在編輯的行

// 單筆新增
const newName   = ref('')
const newLabel  = ref('')

// 批次自動生成
const batchPrefix = ref('')
const batchFrom   = ref(1)
const batchTo     = ref(5)
const batchLabelTpl = ref('{n}')   // {n} 替換為識別碼

// ── Helpers ──────────────────────────────────────────────
function orderUrl(name: string) {
  return `${baseUrl.value}/order/?table=${encodeURIComponent(name)}`
}

async function genQR(id: number, name: string) {
  qrUrls.value[id] = await QRCode.toDataURL(orderUrl(name), {
    width: 120, margin: 1,
    color: { dark: '#000000', light: '#ffffff' },
  })
}

async function genAll() {
  for (const e of entries.value) await genQR(e.id, e.name)
}

function save() {
  localStorage.setItem(STORAGE_KEY,
    JSON.stringify(entries.value.map(({ id: _, ...rest }) => rest)))
}

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    entries.value = raw.map((r: any) => ({ id: ++uid, name: r.name, label: r.label, enabled: r.enabled ?? true }))
  } catch {
    entries.value = []
  }
}

// ── 新增 ─────────────────────────────────────────────────
async function addEntry(name: string, label: string) {
  const id = ++uid
  entries.value.push({ id, name, label: label || name, enabled: true })
  await genQR(id, name)
  save()
}

async function addSingle() {
  const name = newName.value.trim()
  if (!name) return
  await addEntry(name, newLabel.value.trim())
  newName.value  = ''
  newLabel.value = ''
}

async function batchGenerate() {
  const prefix = batchPrefix.value.trim()
  const from = Number(batchFrom.value)
  const to   = Number(batchTo.value)
  if (from > to || to - from > 99) return
  for (let n = from; n <= to; n++) {
    const name  = `${prefix}${n}`
    const label = batchLabelTpl.value.replace('{n}', name)
    await addEntry(name, label)
  }
}

// ── 刪除 ─────────────────────────────────────────────────
function remove(id: number) {
  entries.value = entries.value.filter(e => e.id !== id)
  delete qrUrls.value[id]
  delete editMap.value[id]
  save()
}

// ── 開關 ─────────────────────────────────────────────────
function toggleEnabled(e: Entry) {
  e.enabled = !e.enabled
  save()
}

// ── 編輯 ─────────────────────────────────────────────────
function startEdit(e: Entry) {
  editMap.value[e.id] = { name: e.name, label: e.label }
}
function cancelEdit(id: number) {
  delete editMap.value[id]
}
async function saveEdit(e: Entry) {
  const s = editMap.value[e.id]
  if (!s || !s.name.trim()) return
  const nameChanged = s.name !== e.name
  e.name  = s.name.trim()
  e.label = s.label.trim() || e.name
  delete editMap.value[e.id]
  if (nameChanged) await genQR(e.id, e.name)
  save()
}

// ── 下載 ─────────────────────────────────────────────────
function download(e: Entry) {
  const url = qrUrls.value[e.id]
  if (!url) return
  const a = document.createElement('a')
  a.download = `qr-${e.name}.png`
  a.href = url
  a.click()
}

// ── 複製網址 ─────────────────────────────────────────────
function copyUrl(name: string) {
  navigator.clipboard.writeText(orderUrl(name))
}

// ── 列印 ─────────────────────────────────────────────────
function printAll() {
  window.print()
}

// ── 計算 ─────────────────────────────────────────────────
const enabledCount  = computed(() => entries.value.filter(e => e.enabled).length)
const disabledCount = computed(() => entries.value.length - enabledCount.value)

onMounted(async () => {
  load()
  await genAll()
})
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
          共 {{ entries.length }} 筆・啟用 {{ enabledCount }}・停用 {{ disabledCount }}
        </small>
      </div>
      <button class="btn btn-outline-secondary btn-sm no-print" @click="printAll">
        <i class="bi bi-printer me-1"></i>列印全部
      </button>
    </div>

    <!-- ── 設定卡：網址前綴 ───────────────────────────── -->
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
          QR 碼連結格式：<code>{{ baseUrl }}/order/?table=識別碼</code>
        </div>
      </div>
    </div>

    <!-- ── 新增區 ─────────────────────────────────────── -->
    <div class="row g-3 mb-3 no-print">

      <!-- 單筆新增 -->
      <div class="col-12 col-lg-6">
        <div class="card shadow-sm h-100">
          <div class="card-header py-2 fw-semibold small">
            <i class="bi bi-plus-circle me-1"></i>單筆新增
          </div>
          <div class="card-body py-2">
            <div class="row g-2">
              <div class="col-4">
                <label class="form-label form-label-sm mb-1">識別碼 <span class="text-danger">*</span></label>
                <input v-model="newName" type="text" class="form-control form-control-sm"
                       placeholder="A1" @keyup.enter="addSingle" />
              </div>
              <div class="col-5">
                <label class="form-label form-label-sm mb-1">標籤（選填）</label>
                <input v-model="newLabel" type="text" class="form-control form-control-sm"
                       placeholder="A 區 1 號桌" @keyup.enter="addSingle" />
              </div>
              <div class="col-3 d-flex align-items-end">
                <button class="btn btn-primary btn-sm w-100" @click="addSingle"
                        :disabled="!newName.trim()">
                  <i class="bi bi-plus-lg me-1"></i>新增
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 批次自動生成 -->
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
                       placeholder="{n}" title="{n} 將替換為識別碼" />
              </div>
              <div class="col-2 d-flex align-items-end">
                <button class="btn btn-success btn-sm w-100" @click="batchGenerate"
                        :disabled="batchFrom > batchTo || batchTo - batchFrom > 99">
                  生成
                </button>
              </div>
            </div>
            <div class="form-text mt-1">
              例：前綴「A」從 1 到 5，標籤「{n} 號桌」→ A1～A5 各一張
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 空狀態 ─────────────────────────────────────── -->
    <div v-if="!entries.length" class="text-center text-muted py-5">
      <i class="bi bi-qr-code-scan" style="font-size:3rem;opacity:.3"></i>
      <p class="mt-2 mb-0">尚未新增任何 QR 碼，請使用上方功能新增</p>
    </div>

    <!-- ── 列表 ───────────────────────────────────────── -->
    <div v-else class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light no-print">
            <tr>
              <th style="width:110px">QR 圖片</th>
              <th>識別碼 / 標籤</th>
              <th class="d-none d-md-table-cell">點餐網址</th>
              <th class="text-center no-print" style="width:70px">啟用</th>
              <th class="text-center no-print" style="width:140px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in entries" :key="e.id" :class="{ 'table-secondary text-muted': !e.enabled }">

              <!-- QR 圖片 -->
              <td class="py-2">
                <img v-if="qrUrls[e.id]" :src="qrUrls[e.id]"
                     :alt="`QR ${e.name}`"
                     :style="{ width: '90px', opacity: e.enabled ? 1 : 0.35 }"
                     class="qr-img rounded" />
              </td>

              <!-- 識別碼 / 標籤（一般 or 編輯模式） -->
              <td>
                <template v-if="editMap[e.id]">
                  <div class="d-flex flex-column gap-1" style="max-width:240px">
                    <input v-model="editMap[e.id].name" type="text"
                           class="form-control form-control-sm"
                           placeholder="識別碼" />
                    <input v-model="editMap[e.id].label" type="text"
                           class="form-control form-control-sm"
                           placeholder="標籤" />
                  </div>
                </template>
                <template v-else>
                  <div class="fw-semibold">{{ e.label }}</div>
                  <small class="text-muted font-monospace">{{ e.name }}</small>
                </template>
              </td>

              <!-- 網址（桌機） -->
              <td class="d-none d-md-table-cell">
                <div class="d-flex align-items-center gap-1 no-print">
                  <code class="small text-truncate" style="max-width:260px">
                    {{ orderUrl(e.name) }}
                  </code>
                  <button class="btn btn-link btn-sm p-0 text-muted" @click="copyUrl(e.name)"
                          title="複製網址">
                    <i class="bi bi-clipboard"></i>
                  </button>
                </div>
                <!-- 列印時只顯示文字 -->
                <span class="print-only small">{{ orderUrl(e.name) }}</span>
              </td>

              <!-- 開關 -->
              <td class="text-center no-print">
                <div class="form-check form-switch d-inline-block m-0">
                  <input class="form-check-input" type="checkbox"
                         :checked="e.enabled" @change="toggleEnabled(e)"
                         style="cursor:pointer;width:2.2em;height:1.2em" />
                </div>
              </td>

              <!-- 操作按鈕 -->
              <td class="text-center no-print">
                <template v-if="editMap[e.id]">
                  <button class="btn btn-sm btn-success me-1" @click="saveEdit(e)"
                          :disabled="!editMap[e.id].name.trim()">
                    <i class="bi bi-check-lg"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary" @click="cancelEdit(e.id)">
                    <i class="bi bi-x-lg"></i>
                  </button>
                </template>
                <template v-else>
                  <button class="btn btn-sm btn-outline-primary me-1" @click="startEdit(e)"
                          title="編輯">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary me-1" @click="download(e)"
                          title="下載 PNG">
                    <i class="bi bi-download"></i>
                  </button>
                  <button class="btn btn-sm btn-outline-danger" @click="remove(e.id)"
                          title="刪除">
                    <i class="bi bi-trash3"></i>
                  </button>
                </template>
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

/* 列印 */
@media print {
  .no-print    { display: none !important; }
  .print-only  { display: block !important; }
  th, td       { font-size: .8rem !important; }
  tr           { break-inside: avoid; }
  .qr-img      { width: 80px !important; opacity: 1 !important; }
}
@media screen {
  .print-only  { display: none; }
}
</style>
