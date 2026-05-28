<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import { useCacheStore } from '@/stores/cache'
import http from '@/api'

const toast = useToastStore()
const cache = useCacheStore()

// ── 後端支援的平台 ───────────────────────────────────
const PLATFORMS = [
  { key: 'ubereats',  name: 'UberEats',  icon: 'bi-bicycle',   color: '#06c167' },
  { key: 'foodpanda', name: 'foodpanda', icon: 'bi-bag-heart-fill', color: '#d70f64' },
] as const

type PlatformKey = 'ubereats' | 'foodpanda'

interface PlatformSettings {
  platform:             string
  enabled:              boolean
  auto_confirm:         boolean
  default_warehouse_id: string
  webhook_url?:         string
  last_sync?:           string | null
}

const loading      = ref(false)
const saving       = ref<PlatformKey | ''>('')
const syncingMenu  = ref<PlatformKey | ''>('')

// 每個平台各一份 form 資料
const forms = ref<Record<PlatformKey, PlatformSettings>>({
  ubereats: {
    platform: 'ubereats', enabled: false, auto_confirm: false, default_warehouse_id: '', webhook_url: '', last_sync: null,
  },
  foodpanda: {
    platform: 'foodpanda', enabled: false, auto_confirm: false, default_warehouse_id: '', webhook_url: '', last_sync: null,
  },
})

// ── Load ───────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [ue, fp] = await Promise.all([
      http.get('/delivery/settings/ubereats'),
      http.get('/delivery/settings/foodpanda'),
    ])
    forms.value.ubereats  = { ...forms.value.ubereats,  ...(ue.data.data || {}) }
    forms.value.foodpanda = { ...forms.value.foodpanda, ...(fp.data.data || {}) }
  } catch {
    toast.show('載入外送設定失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Save ───────────────────────────────────────────
async function save(platform: PlatformKey) {
  saving.value = platform
  try {
    const f = forms.value[platform]
    await http.put(`/delivery/settings/${platform}`, {
      enabled:              f.enabled,
      auto_confirm:         f.auto_confirm,
      default_warehouse_id: f.default_warehouse_id || '',
    })
    toast.show(`${PLATFORMS.find(p => p.key === platform)?.name} 設定已儲存`, 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = ''
  }
}

// ── Sync orders ────────────────────────────────────
async function syncOrders(platform: PlatformKey) {
  saving.value = platform
  try {
    const res = await http.post(`/delivery/sync/${platform}`)
    const d = res.data
    toast.show(`同步完成：新增 ${d.new_count} 筆`, 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '同步失敗', 'danger')
  } finally {
    saving.value = ''
  }
}

// ── Sync menu from platform ────────────────────────
async function syncMenu(platform: PlatformKey) {
  syncingMenu.value = platform
  try {
    const res = await http.post(`/delivery/menu/sync/${platform}`)
    const d = res.data
    const groupMsg = (d.groups_created || d.groups_updated)
      ? `，選項組 新增 ${d.groups_created ?? 0} / 更新 ${d.groups_updated ?? 0}`
      : ''
    toast.show(
      `菜單匯入完成：新增 ${d.created} 筆、更新 ${d.updated} 筆${groupMsg}`,
      'success'
    )
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '匯入菜單失敗', 'danger')
  } finally {
    syncingMenu.value = ''
  }
}

function fmtTime(iso?: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  await cache.loadAll()
  await load()
})
</script>

<template>
  <div>
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary"></div>
    </div>

    <div v-else class="row g-3">
      <div
        v-for="p in PLATFORMS"
        :key="p.key"
        class="col-12 col-lg-6"
      >
        <div class="table-card">
          <!-- 標題 -->
          <div class="table-header">
            <h6 class="mb-0 d-flex align-items-center gap-2">
              <i :class="`bi ${p.icon}`" :style="`color:${p.color}`"></i>
              {{ p.name }}
              <span
                class="badge ms-1"
                :class="forms[p.key].enabled ? 'bg-success' : 'bg-secondary'"
              >
                {{ forms[p.key].enabled ? '啟用' : '停用' }}
              </span>
            </h6>
            <div class="d-flex gap-2">
              <button
                class="btn btn-sm btn-outline-secondary"
                :disabled="saving === p.key || syncingMenu === p.key"
                @click="syncOrders(p.key)"
                title="主動拉取最新訂單"
              >
                <span v-if="saving === p.key" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-arrow-repeat me-1"></i>同步訂單
              </button>
              <button
                class="btn btn-sm btn-outline-primary"
                :disabled="saving === p.key || syncingMenu === p.key"
                @click="syncMenu(p.key)"
                title="從平台拉取菜單（含客製化選項組）到菜單管理"
              >
                <span v-if="syncingMenu === p.key" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-cloud-download me-1"></i>匯入菜單
              </button>
            </div>
          </div>

          <div class="p-3">
            <!-- 啟用 -->
            <div class="mb-3 d-flex align-items-center justify-content-between">
              <div>
                <div class="fw-semibold">啟用整合</div>
                <div class="text-muted small">開啟後系統會接收此平台的 Webhook 通知</div>
              </div>
              <div class="form-check form-switch mb-0">
                <input
                  v-model="forms[p.key].enabled"
                  class="form-check-input"
                  type="checkbox"
                  :id="`${p.key}-enabled`"
                  role="switch"
                />
              </div>
            </div>

            <hr class="my-2" />

            <!-- 自動接單 -->
            <div class="mb-3 d-flex align-items-center justify-content-between">
              <div>
                <div class="fw-semibold">自動接單</div>
                <div class="text-muted small">收到新訂單後自動確認，並建立 POS 銷售紀錄</div>
              </div>
              <div class="form-check form-switch mb-0">
                <input
                  v-model="forms[p.key].auto_confirm"
                  class="form-check-input"
                  type="checkbox"
                  :id="`${p.key}-auto`"
                  role="switch"
                />
              </div>
            </div>

            <hr class="my-2" />

            <!-- 預設倉庫 -->
            <div class="mb-3">
              <label :for="`${p.key}-wh`" class="form-label fw-semibold">
                預設倉庫
                <span class="text-muted small">（自動接單時扣減庫存的倉庫）</span>
              </label>
              <select
                v-model="forms[p.key].default_warehouse_id"
                :id="`${p.key}-wh`"
                class="form-select"
              >
                <option value="">— 不指定 —</option>
                <option
                  v-for="wh in cache.warehouses"
                  :key="wh._id"
                  :value="wh._id"
                >{{ wh.name }}</option>
              </select>
            </div>

            <!-- 上次同步 -->
            <div class="text-muted small mb-3">
              <i class="bi bi-clock-history me-1"></i>
              上次同步：{{ fmtTime(forms[p.key].last_sync) }}
            </div>

            <!-- 儲存 -->
            <button
              class="btn btn-primary w-100"
              :disabled="saving === p.key"
              @click="save(p.key)"
            >
              <span v-if="saving === p.key" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-floppy me-1"></i>儲存設定
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 說明卡片 -->
    <div class="table-card mt-3 p-3">
      <h6 class="fw-bold mb-3"><i class="bi bi-info-circle me-1 text-primary"></i>Webhook 設定說明</h6>
      <p class="text-muted small mb-2">
        將以下 Webhook URL 填入對應平台的開發者後台，平台有新訂單時會主動推播給本系統：
      </p>
      <div class="row g-2">
        <div class="col-12 col-md-6">
          <div class="fw-semibold small mb-1">UberEats</div>
          <code class="d-block p-2 bg-light rounded small text-break">
            https://{{ window?.location?.hostname || 'yourdomain.com' }}/delivery/webhook/ubereats
          </code>
        </div>
        <div class="col-12 col-md-6">
          <div class="fw-semibold small mb-1">foodpanda</div>
          <code class="d-block p-2 bg-light rounded small text-break">
            https://{{ window?.location?.hostname || 'yourdomain.com' }}/delivery/webhook/foodpanda
          </code>
        </div>
      </div>
      <p class="text-muted small mt-2 mb-0">
        <i class="bi bi-exclamation-triangle me-1 text-warning"></i>
        API 金鑰（UBEREATS_CLIENT_SECRET / FOODPANDA_API_KEY 等）請在伺服器的 <code>.env</code> 檔案中設定，不在此頁面管理。
      </p>
    </div>
  </div>
</template>
