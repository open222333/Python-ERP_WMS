<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import { useCacheStore } from '@/stores/cache'
import http from '@/api'

const toast = useToastStore()
const cache = useCacheStore()

const PLATFORMS = [
  { key: 'ubereats',  name: 'UberEats',  icon: 'bi-bicycle',       color: '#06c167' },
  { key: 'foodpanda', name: 'foodpanda', icon: 'bi-bag-heart-fill', color: '#d70f64' },
] as const
type PlatformKey = 'ubereats' | 'foodpanda'

interface StoreRow {
  store_id:   string
  store_name: string
  store_code: string
  platforms:  Record<string, { enabled: boolean; auto_confirm: boolean }>
}

interface PlatformForm {
  enabled:              boolean
  auto_confirm:         boolean
  default_warehouse_id: string
}

const loading   = ref(false)
const saving    = ref<PlatformKey | ''>('')
const storeList = ref<StoreRow[]>([])

const showModal        = ref(false)
const editingStoreId   = ref('')
const editingStoreName = ref('')
const activePlatform   = ref<PlatformKey>('ubereats')

const forms = ref<Record<PlatformKey, PlatformForm>>({
  ubereats:  { enabled: false, auto_confirm: false, default_warehouse_id: '' },
  foodpanda: { enabled: false, auto_confirm: false, default_warehouse_id: '' },
})

async function load() {
  loading.value = true
  try {
    const r = await http.get('/delivery/store/')
    storeList.value = r.data.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function openModal(store: StoreRow) {
  editingStoreId.value   = store.store_id
  editingStoreName.value = store.store_name
  activePlatform.value   = 'ubereats'
  forms.value = {
    ubereats:  { enabled: false, auto_confirm: false, default_warehouse_id: '' },
    foodpanda: { enabled: false, auto_confirm: false, default_warehouse_id: '' },
  }
  showModal.value = true
  try {
    const [ue, fp] = await Promise.all([
      http.get(`/delivery/store/${store.store_id}/settings/ubereats`),
      http.get(`/delivery/store/${store.store_id}/settings/foodpanda`),
    ])
    const merge = (key: PlatformKey, data: any) => {
      const d = data?.data || {}
      forms.value[key] = {
        enabled:              !!d.enabled,
        auto_confirm:         !!d.auto_confirm,
        default_warehouse_id: d.default_warehouse_id || '',
      }
    }
    merge('ubereats', ue.data)
    merge('foodpanda', fp.data)
  } catch {
    toast.show('載入設定失敗', 'danger')
  }
}

async function savePlatform(platform: PlatformKey) {
  saving.value = platform
  try {
    await http.put(`/delivery/store/${editingStoreId.value}/settings/${platform}`, forms.value[platform])
    toast.show(`${PLATFORMS.find(p => p.key === platform)?.name} 設定已儲存`, 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = ''
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
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-scooter me-1"></i>外送平台設定</h6>
    </div>

    <div v-if="loading" class="text-center py-4">
      <div class="spinner-border spinner-border-sm text-primary"></div>
    </div>

    <div v-else class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>店家</th>
            <th>代碼</th>
            <th v-for="p in PLATFORMS" :key="p.key">
              <i :class="`bi ${p.icon} me-1`" :style="`color:${p.color}`"></i>{{ p.name }}
            </th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!storeList.length">
            <td :colspan="2 + PLATFORMS.length + 1" class="text-center text-muted py-3">尚無店家資料</td>
          </tr>
          <tr v-for="s in storeList" :key="s.store_id">
            <td class="fw-semibold">{{ s.store_name }}</td>
            <td><code>{{ s.store_code || '—' }}</code></td>
            <td v-for="p in PLATFORMS" :key="p.key">
              <span class="badge"
                    :class="s.platforms[p.key]?.enabled ? 'bg-success' : 'bg-secondary'">
                {{ s.platforms[p.key]?.enabled ? '啟用' : '停用' }}
              </span>
            </td>
            <td>
              <button class="btn btn-sm btn-outline-primary" @click="openModal(s)">
                <i class="bi bi-gear me-1"></i>設定
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Settings Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055"
         @click.self="showModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-scooter me-1"></i>外送平台設定 ─ {{ editingStoreName }}
            </h5>
            <button class="btn-close" @click="showModal = false"></button>
          </div>
          <div class="modal-body">
            <!-- Platform tabs -->
            <ul class="nav nav-tabs mb-3">
              <li v-for="p in PLATFORMS" :key="p.key" class="nav-item">
                <a class="nav-link d-flex align-items-center gap-1"
                   :class="{ active: activePlatform === p.key }"
                   href="#" @click.prevent="activePlatform = p.key">
                  <i :class="`bi ${p.icon}`" :style="`color:${p.color}`"></i>
                  {{ p.name }}
                </a>
              </li>
            </ul>

            <template v-for="p in PLATFORMS" :key="p.key">
              <div v-if="activePlatform === p.key">
                <!-- 啟用 -->
                <div class="d-flex align-items-center justify-content-between mb-3 p-3 bg-light rounded">
                  <div>
                    <div class="fw-semibold">啟用整合</div>
                    <div class="text-muted small">開啟後系統會接收此平台的 Webhook 通知</div>
                  </div>
                  <div class="form-check form-switch mb-0">
                    <input v-model="forms[p.key].enabled" class="form-check-input" type="checkbox"
                           :id="`${p.key}-enabled`" style="width:2.5em;height:1.3em;cursor:pointer" />
                  </div>
                </div>

                <!-- 自動接單 -->
                <div class="d-flex align-items-center justify-content-between mb-3 p-3 border rounded">
                  <div>
                    <div class="fw-semibold">自動接單</div>
                    <div class="text-muted small">收到新訂單後自動確認，並建立 POS 銷售紀錄</div>
                  </div>
                  <div class="form-check form-switch mb-0">
                    <input v-model="forms[p.key].auto_confirm" class="form-check-input" type="checkbox"
                           :id="`${p.key}-auto`" style="width:2.5em;height:1.3em;cursor:pointer" />
                  </div>
                </div>

                <!-- 預設倉庫 -->
                <div class="mb-3">
                  <label class="form-label fw-semibold">
                    預設倉庫 <span class="text-muted small">（自動接單時扣減庫存的倉庫）</span>
                  </label>
                  <select v-model="forms[p.key].default_warehouse_id" class="form-select">
                    <option value="">— 不指定 —</option>
                    <option v-for="wh in cache.warehouses" :key="wh._id" :value="wh._id">
                      {{ wh.name }}
                    </option>
                  </select>
                </div>

                <button
                  class="btn btn-primary"
                  :disabled="saving === p.key"
                  @click="savePlatform(p.key)"
                >
                  <span v-if="saving === p.key" class="spinner-border spinner-border-sm me-1"></span>
                  <i v-else class="bi bi-floppy me-1"></i>儲存 {{ p.name }} 設定
                </button>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showModal = false">關閉</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Webhook 說明 -->
  <div class="table-card mt-3 p-3">
    <h6 class="fw-bold mb-3"><i class="bi bi-info-circle me-1 text-primary"></i>Webhook 設定說明</h6>
    <p class="text-muted small mb-2">將以下 Webhook URL 填入對應平台的開發者後台：</p>
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
  </div>
</template>
