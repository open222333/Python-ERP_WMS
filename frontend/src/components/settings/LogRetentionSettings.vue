<!-- [U10] 自 views/admin/SettingsView.vue 拆出 -->
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import http from '@/api'
import { parseServerDate } from '@/utils/format'
import { useToastStore } from '@/stores/toast'
import { appConfirm } from '@/composables/useConfirm'

/** 保留天數與上次清除時間由 SettingsView 載入 /settings/ 後傳入；統計數字由本元件呼叫 /log/stats */
const props = defineProps<{ initialDays: number; initialLastCleanup: string | null }>()

const toast = useToastStore()

const logRetentionDays = ref(0)
const logTotal         = ref<number | null>(null)
const logOlderCount    = ref<number | null>(null)
const logLastCleanup   = ref<string | null>(null)
const savingLog        = ref(false)
const cleaningLog      = ref(false)

watch(() => props.initialDays, v => { logRetentionDays.value = Number(v ?? 0) }, { immediate: true })
watch(() => props.initialLastCleanup, v => { if (v) logLastCleanup.value = v }, { immediate: true })

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
  if (!(await appConfirm(`確認清除 ${logRetentionDays.value} 天前的操作紀錄？此操作無法復原。`, { danger: true }))) return
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
  return (parseServerDate(iso) ?? new Date(iso)).toLocaleString('zh-TW', {   // [U4]
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

onMounted(loadLogStats)
</script>

<template>
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
            <div class="p-3 bg-body-tertiary rounded border">
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
</template>
