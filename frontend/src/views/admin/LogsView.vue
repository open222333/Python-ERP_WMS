<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'

const toast   = useToastStore()
const logs    = ref<any[]>([])
const loading = ref(false)
const fUser   = ref('')
const fAction = ref('')
const fStart  = ref('')
const fEnd    = ref('')
const limit   = ref(200)

const importing  = ref(false)
const exporting  = ref(false)
const fileInput  = ref<HTMLInputElement>()

// ── 讀取 ──────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (fUser.value)   params.set('username',   fUser.value)
    if (fAction.value) params.set('action',     fAction.value)
    if (fStart.value)  params.set('start_date', fStart.value)
    if (fEnd.value)    params.set('end_date',   fEnd.value)
    params.set('limit', String(limit.value))
    const { data } = await http.get(`/log/?${params}`)
    logs.value = data?.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── 匯出 CSV ──────────────────────────────────────────
async function exportCsv() {
  exporting.value = true
  try {
    const params = new URLSearchParams()
    if (fUser.value)   params.set('username',   fUser.value)
    if (fAction.value) params.set('action',     fAction.value)
    if (fStart.value)  params.set('start_date', fStart.value)
    if (fEnd.value)    params.set('end_date',   fEnd.value)

    // 用原生 fetch 取得 blob，以觸發下載
    const token = localStorage.getItem('token')
    const res = await fetch(`/log/export?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('匯出失敗')
    const blob = await res.blob()

    // 取伺服器指定的檔名（或自訂）
    const cd   = res.headers.get('Content-Disposition') || ''
    const match = cd.match(/filename="?([^"]+)"?/)
    const name  = match ? match[1] : `logs_${new Date().toISOString().slice(0, 10)}.csv`

    const url = URL.createObjectURL(blob)
    const a   = document.createElement('a')
    a.href = url; a.download = name; a.click()
    URL.revokeObjectURL(url)
    toast.show(`已匯出 ${logs.value.length > 0 ? '' : '全部'}紀錄`, 'success')
  } catch (e: any) {
    toast.show(e?.message || '匯出失敗', 'danger')
  } finally {
    exporting.value = false
  }
}

// ── 匯入 CSV / JSON ────────────────────────────────────
function openImport() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await http.post('/log/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    toast.show(`匯入完成：共 ${data.inserted} 筆`, 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '匯入失敗', 'danger')
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-journal-text me-1"></i>操作紀錄</h6>
      <div class="toolbar flex-wrap gap-1">
        <!-- 搜尋條件 -->
        <input
          v-model="fUser"
          type="text"
          class="form-control form-control-sm"
          style="width:110px"
          placeholder="使用者"
          @keydown.enter="(e) => !e.isComposing && load()"
        />
        <input
          v-model="fAction"
          type="text"
          class="form-control form-control-sm"
          style="width:110px"
          placeholder="操作類型"
          @keydown.enter="(e) => !e.isComposing && load()"
        />
        <input
          v-model="fStart"
          type="date"
          class="form-control form-control-sm"
          style="width:140px"
          title="開始日期"
          @change="load"
        />
        <span class="text-muted small align-self-center">—</span>
        <input
          v-model="fEnd"
          type="date"
          class="form-control form-control-sm"
          style="width:140px"
          title="結束日期"
          @change="load"
        />
        <!-- 顯示筆數 -->
        <select v-model.number="limit" class="form-select form-select-sm" style="width:90px" @change="load">
          <option :value="100">100 筆</option>
          <option :value="200">200 筆</option>
          <option :value="500">500 筆</option>
          <option :value="1000">1000 筆</option>
        </select>
        <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load">
          <i class="bi bi-search"></i>
        </button>
        <!-- 匯出 -->
        <button
          class="btn btn-sm btn-outline-success"
          :disabled="exporting"
          @click="exportCsv"
          title="依目前篩選條件匯出全部紀錄為 CSV（不受筆數限制）"
        >
          <span v-if="exporting" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-download me-1"></i>匯出 CSV
        </button>
        <!-- 匯入 -->
        <button
          class="btn btn-sm btn-outline-primary"
          :disabled="importing"
          @click="openImport"
          title="從 CSV 或 JSON 檔案匯入操作紀錄（需 admin 權限）"
        >
          <span v-if="importing" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-upload me-1"></i>匯入
        </button>
        <!-- 隱藏 file input -->
        <input
          ref="fileInput"
          type="file"
          accept=".csv,.json"
          style="display:none"
          @change="onFileChange"
        />
      </div>
    </div>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>使用者</th>
            <th>操作</th>
            <th>詳情</th>
            <th>結果</th>
            <th>時間</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!logs.length">
            <td colspan="5" class="text-center text-muted py-3">無紀錄</td>
          </tr>
          <tr v-for="l in logs" :key="l._id">
            <td><strong>{{ l.username || l.operator || '-' }}</strong></td>
            <td>{{ l.action }}</td>
            <td
              class="text-muted small"
              style="max-width:320px; word-break:break-all"
            >{{ l.detail || '-' }}</td>
            <td>
              <span
                class="badge"
                :class="l.success !== false ? 'bg-success' : 'bg-danger'"
              >{{ l.success !== false ? '成功' : '失敗' }}</span>
            </td>
            <td class="text-muted small text-nowrap">{{ fmtDate(l.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="p-2 px-3 text-muted small border-top d-flex align-items-center gap-3">
      <span>顯示 {{ logs.length }} 筆（上限 {{ limit }}）</span>
      <span v-if="logs.length >= limit" class="text-warning">
        <i class="bi bi-exclamation-triangle me-1"></i>已達上限，可調高篩選或縮小日期範圍
      </span>
    </div>
  </div>
</template>
