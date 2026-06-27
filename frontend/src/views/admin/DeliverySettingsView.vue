<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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

interface SystemItem  { product_id: string; product_name: string; qty: number }
interface ItemMapping { platform_item_name: string; system_items: SystemItem[] }
interface Template    { _id: string; name: string; platform: string; items: ItemMapping[] }

// ── 主 tab ──────────────────────────────────────────────────
const mainTab = ref<'stores' | 'templates'>('stores')

// ── 品項對應模板 ─────────────────────────────────────────────
const templates    = ref<Template[]>([])
const loadingTpl   = ref(false)
const showTplModal = ref(false)
const editingTplId = ref<string | null>(null)
const tplForm      = ref({ name: '', platform: '', items: [] as ItemMapping[] })
const tplSaving    = ref(false)
const tplDeleting  = ref('')

const tplAddingMapping = ref(false)
const tplNewMapping    = ref<ItemMapping>({ platform_item_name: '', system_items: [] })
const tplProductSearch = ref('')

const filteredTplProducts = computed(() => {
  const kw = tplProductSearch.value.trim().toLowerCase()
  return kw
    ? cache.products.filter((p: any) =>
        p.name.toLowerCase().includes(kw) || (p.sku || '').toLowerCase().includes(kw))
    : cache.products.slice(0, 30)
})

async function loadTemplates() {
  loadingTpl.value = true
  try {
    const r = await http.get('/delivery/mapping-templates/')
    templates.value = r.data.data || []
  } catch {
    toast.show('載入模板失敗', 'danger')
  } finally {
    loadingTpl.value = false
  }
}

function openTplModal(tpl?: Template) {
  tplAddingMapping.value = false
  tplNewMapping.value    = { platform_item_name: '', system_items: [] }
  tplProductSearch.value = ''
  if (tpl) {
    editingTplId.value = tpl._id
    tplForm.value = {
      name:     tpl.name,
      platform: tpl.platform || '',
      items:    tpl.items.map(m => ({
        platform_item_name: m.platform_item_name,
        system_items: m.system_items.map(s => ({ ...s })),
      })),
    }
  } else {
    editingTplId.value = null
    tplForm.value = { name: '', platform: '', items: [] }
  }
  showTplModal.value = true
}

async function saveTpl() {
  if (!tplForm.value.name.trim()) { toast.show('請填寫模板名稱', 'danger'); return }
  tplSaving.value = true
  try {
    const payload = { ...tplForm.value, name: tplForm.value.name.trim() }
    if (editingTplId.value) {
      await http.put(`/delivery/mapping-templates/${editingTplId.value}/`, payload)
    } else {
      await http.post('/delivery/mapping-templates/', payload)
    }
    toast.show('模板已儲存', 'success')
    showTplModal.value = false
    await loadTemplates()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    tplSaving.value = false
  }
}

async function delTpl(tpl: Template) {
  if (!confirm(`確定要刪除模板「${tpl.name}」？`)) return
  tplDeleting.value = tpl._id
  try {
    await http.delete(`/delivery/mapping-templates/${tpl._id}/`)
    toast.show('已刪除', 'success')
    await loadTemplates()
  } catch {
    toast.show('刪除失敗', 'danger')
  } finally {
    tplDeleting.value = ''
  }
}

function tplStartAddMapping() {
  tplNewMapping.value    = { platform_item_name: '', system_items: [] }
  tplProductSearch.value = ''
  tplAddingMapping.value = true
}
function tplCancelAddMapping() { tplAddingMapping.value = false }

function tplAddProduct(product: any) {
  if (!tplNewMapping.value.system_items.find(s => s.product_id === product._id))
    tplNewMapping.value.system_items.push({ product_id: product._id, product_name: product.name, qty: 1 })
}
function tplRemoveProduct(idx: number) { tplNewMapping.value.system_items.splice(idx, 1) }

function tplConfirmAddMapping() {
  if (!tplNewMapping.value.platform_item_name.trim()) {
    toast.show('請填寫平台品項名稱', 'danger'); return
  }
  tplForm.value.items.push({
    platform_item_name: tplNewMapping.value.platform_item_name.trim(),
    system_items:       [...tplNewMapping.value.system_items],
  })
  tplAddingMapping.value = false
}
function tplRemoveMapping(idx: number) { tplForm.value.items.splice(idx, 1) }

// ── 店家設定 ─────────────────────────────────────────────────
interface StoreRow {
  store_id: string; store_name: string; store_code: string
  platforms: Record<string, { enabled: boolean; auto_confirm: boolean }>
}
interface PlatformForm {
  enabled: boolean; auto_confirm: boolean
  default_warehouse_id: string; mapping_template_id: string
}

const loading   = ref(false)
const saving    = ref<PlatformKey | ''>('')
const storeList = ref<StoreRow[]>([])

const showModal        = ref(false)
const editingStoreId   = ref('')
const editingStoreName = ref('')
const activePlatform   = ref<PlatformKey>('ubereats')

const emptyForm = (): PlatformForm => ({
  enabled: false, auto_confirm: false, default_warehouse_id: '', mapping_template_id: '',
})

const forms = ref<Record<PlatformKey, PlatformForm>>({
  ubereats:  emptyForm(),
  foodpanda: emptyForm(),
})

const storeWarehouses = computed(() =>
  editingStoreId.value
    ? cache.warehouses.filter((wh: any) => wh.store_id === editingStoreId.value)
    : cache.warehouses
)

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
  forms.value = { ubereats: emptyForm(), foodpanda: emptyForm() }
  showModal.value = true
  try {
    const [ue, fp] = await Promise.all([
      http.get(`/delivery/store/${store.store_id}/settings/ubereats`),
      http.get(`/delivery/store/${store.store_id}/settings/foodpanda`),
    ])
    const merge = (key: PlatformKey, resp: any) => {
      const d  = resp?.data || {}
      const wh = d.default_warehouse_id || storeWarehouses.value[0]?._id || ''
      forms.value[key] = {
        enabled:              !!d.enabled,
        auto_confirm:         !!d.auto_confirm,
        default_warehouse_id: wh,
        mapping_template_id:  d.mapping_template_id || '',
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
    await http.put(
      `/delivery/store/${editingStoreId.value}/settings/${platform}`,
      forms.value[platform],
    )
    toast.show(`${PLATFORMS.find(p => p.key === platform)?.name} 設定已儲存`, 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = ''
  }
}

onMounted(async () => {
  await cache.loadAll()
  await Promise.all([load(), loadTemplates()])
})
</script>

<template>
  <!-- ─── 標題 + 主 tab ──────────────────────────────────── -->
  <div class="d-flex align-items-center mb-3 gap-2">
    <h5 class="mb-0"><i class="bi bi-scooter me-2"></i>外送平台設定</h5>
  </div>

  <ul class="nav nav-tabs mb-3">
    <li class="nav-item">
      <button class="nav-link" :class="{ active: mainTab === 'stores' }"
              @click="mainTab = 'stores'">
        <i class="bi bi-shop me-1"></i>店家設定
      </button>
    </li>
    <li class="nav-item">
      <button class="nav-link" :class="{ active: mainTab === 'templates' }"
              @click="mainTab = 'templates'">
        <i class="bi bi-diagram-3 me-1"></i>品項對應模板
      </button>
    </li>
  </ul>

  <div class="table-card mb-0">
    <!-- ─── 店家設定 tab ─────────────────────────────────── -->
    <template v-if="mainTab === 'stores'">
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
                <span class="badge" :class="s.platforms[p.key]?.enabled ? 'bg-success' : 'bg-secondary'">
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
    </template>

    <!-- ─── 品項對應模板 tab ─────────────────────────────── -->
    <template v-else>
      <div class="d-flex align-items-center px-3 py-2 border-bottom">
        <span class="text-muted small">建立品項對應模板（平台品項 → 系統產品），再由各店家的平台設定中綁定。</span>
        <button class="btn btn-sm btn-primary ms-3 flex-shrink-0" @click="openTplModal()">
          <i class="bi bi-plus-lg me-1"></i>新增模板
        </button>
      </div>
      <div v-if="loadingTpl" class="text-center py-4">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else class="table-responsive">
        <table class="table mb-0">
          <thead>
            <tr>
              <th>模板名稱</th>
              <th>適用平台</th>
              <th>品項數</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!templates.length">
              <td colspan="4" class="text-center text-muted py-3">尚無模板，點「新增模板」建立</td>
            </tr>
            <tr v-for="tpl in templates" :key="tpl._id">
              <td class="fw-semibold">{{ tpl.name }}</td>
              <td>
                <span v-if="tpl.platform" class="badge bg-secondary">
                  {{ PLATFORMS.find(p => p.key === tpl.platform)?.name || tpl.platform }}
                </span>
                <span v-else class="text-muted small">通用</span>
              </td>
              <td>{{ tpl.items?.length || 0 }} 筆</td>
              <td>
                <button class="btn btn-sm btn-outline-secondary me-1" @click="openTplModal(tpl)">
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger"
                        :disabled="tplDeleting === tpl._id" @click="delTpl(tpl)">
                  <span v-if="tplDeleting === tpl._id" class="spinner-border spinner-border-sm"></span>
                  <i v-else class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>

  <!-- ─── Store Settings Modal ──────────────────────────────── -->
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
                <button class="nav-link d-flex align-items-center gap-1"
                        :class="{ active: activePlatform === p.key }"
                        @click="activePlatform = p.key">
                  <i :class="`bi ${p.icon}`" :style="`color:${p.color}`"></i>
                  {{ p.name }}
                </button>
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
                    <option v-for="wh in storeWarehouses" :key="wh._id" :value="wh._id">
                      {{ wh.name }}
                    </option>
                  </select>
                  <div v-if="storeWarehouses.length === 0" class="form-text text-warning">
                    此店家尚未建立倉庫，請先至「倉庫管理」新增。
                  </div>
                </div>

                <!-- 品項對應模板 -->
                <div class="mb-4">
                  <label class="form-label fw-semibold">
                    <i class="bi bi-diagram-3 me-1 text-primary"></i>品項對應模板
                  </label>
                  <select v-model="forms[p.key].mapping_template_id" class="form-select">
                    <option value="">— 不使用模板 —</option>
                    <option v-for="tpl in templates" :key="tpl._id" :value="tpl._id">
                      {{ tpl.name }}
                      <template v-if="tpl.platform">
                        （{{ PLATFORMS.find(pl => pl.key === tpl.platform)?.name || tpl.platform }}）
                      </template>
                    </option>
                  </select>
                  <div class="form-text">
                    如需新增或修改模板內容，請至「品項對應模板」tab 編輯。
                  </div>
                </div>

                <button class="btn btn-primary" :disabled="saving === p.key"
                        @click="savePlatform(p.key)">
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

  <!-- ─── Template Create/Edit Modal ──────────────────────── -->
  <Teleport to="body">
    <div v-if="showTplModal" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1060"
         @click.self="showTplModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-diagram-3 me-1"></i>
              {{ editingTplId ? '編輯品項對應模板' : '新增品項對應模板' }}
            </h5>
            <button class="btn-close" @click="showTplModal = false"></button>
          </div>
          <div class="modal-body">
            <!-- 模板名稱 -->
            <div class="mb-3">
              <label class="form-label fw-semibold">模板名稱 <span class="text-danger">*</span></label>
              <input v-model="tplForm.name" type="text" class="form-control"
                     placeholder="例：foodpanda 週末套餐" />
            </div>

            <!-- 適用平台 -->
            <div class="mb-4">
              <label class="form-label fw-semibold">
                適用平台 <span class="text-muted small">（選填，僅作分類標記）</span>
              </label>
              <select v-model="tplForm.platform" class="form-select">
                <option value="">通用（不限平台）</option>
                <option v-for="p in PLATFORMS" :key="p.key" :value="p.key">{{ p.name }}</option>
              </select>
            </div>

            <!-- 品項對應清單 -->
            <div>
              <div class="d-flex align-items-center justify-content-between mb-2">
                <div class="fw-semibold">
                  <i class="bi bi-diagram-3 me-1 text-primary"></i>品項對應清單
                  <span class="text-muted small ms-1">（平台品項 → 系統內產品）</span>
                </div>
                <button v-if="!tplAddingMapping" class="btn btn-sm btn-outline-primary"
                        @click="tplStartAddMapping">
                  <i class="bi bi-plus-lg me-1"></i>新增對應
                </button>
              </div>

              <!-- 現有對應 -->
              <div v-if="tplForm.items.length" class="list-group mb-2">
                <div v-for="(m, idx) in tplForm.items" :key="idx"
                     class="list-group-item py-2 px-3">
                  <div class="d-flex align-items-start justify-content-between gap-2">
                    <div class="flex-grow-1">
                      <span class="fw-semibold">{{ m.platform_item_name }}</span>
                      <i class="bi bi-arrow-right mx-2 text-muted"></i>
                      <template v-if="m.system_items.length">
                        <span v-for="(si, si_idx) in m.system_items" :key="si_idx"
                              class="badge bg-light text-dark border me-1">
                          {{ si.product_name }}
                          <span class="text-muted ms-1">×{{ si.qty }}</span>
                        </span>
                      </template>
                      <span v-else class="text-muted small">（無品項）</span>
                    </div>
                    <button class="btn btn-sm btn-outline-danger flex-shrink-0"
                            @click="tplRemoveMapping(idx)">
                      <i class="bi bi-trash"></i>
                    </button>
                  </div>
                </div>
              </div>
              <div v-else-if="!tplAddingMapping" class="text-muted small mb-2">
                尚無品項對應，點「新增對應」開始設定。
              </div>

              <!-- 新增對應表單 -->
              <div v-if="tplAddingMapping" class="border rounded p-3 bg-light">
                <div class="mb-2">
                  <label class="form-label fw-semibold small mb-1">平台品項名稱</label>
                  <input v-model="tplNewMapping.platform_item_name" type="text"
                         class="form-control form-control-sm"
                         placeholder="例：套餐A、大份炒飯..." />
                </div>

                <!-- 已選系統品項 -->
                <div v-if="tplNewMapping.system_items.length" class="mb-2">
                  <div class="text-muted small mb-1">已選系統品項：</div>
                  <div class="d-flex flex-wrap gap-1">
                    <span v-for="(si, idx) in tplNewMapping.system_items" :key="idx"
                          class="badge bg-primary d-flex align-items-center gap-1">
                      {{ si.product_name }}
                      <input v-model.number="si.qty" type="number" min="1"
                             class="form-control form-control-sm d-inline-block p-0"
                             style="width:2.5rem;background:transparent;border:none;color:inherit;font-weight:bold" />
                      <i class="bi bi-x-circle" style="cursor:pointer"
                         @click="tplRemoveProduct(idx)"></i>
                    </span>
                  </div>
                </div>

                <!-- 搜尋產品 -->
                <div class="mb-2">
                  <label class="form-label fw-semibold small mb-1">搜尋系統產品</label>
                  <input v-model="tplProductSearch" type="text" class="form-control form-control-sm"
                         placeholder="輸入名稱或 SKU 搜尋..." />
                  <div class="border rounded mt-1" style="max-height:160px;overflow-y:auto">
                    <div v-if="!filteredTplProducts.length" class="text-muted small p-2">無符合產品</div>
                    <button v-for="prod in filteredTplProducts" :key="prod._id"
                            class="btn btn-sm w-100 text-start rounded-0 border-0 border-bottom"
                            :class="tplNewMapping.system_items.find(s => s.product_id === prod._id)
                                      ? 'btn-light text-muted' : 'btn-white'"
                            @click="tplAddProduct(prod)">
                      <i class="bi bi-check2 me-1"
                         v-if="tplNewMapping.system_items.find(s => s.product_id === prod._id)"></i>
                      {{ prod.name }}
                      <code class="ms-1 text-secondary" style="font-size:.7rem">{{ prod.sku }}</code>
                    </button>
                  </div>
                </div>

                <div class="d-flex gap-2 mt-2">
                  <button class="btn btn-sm btn-primary" @click="tplConfirmAddMapping">
                    <i class="bi bi-check-lg me-1"></i>確認新增
                  </button>
                  <button class="btn btn-sm btn-outline-secondary" @click="tplCancelAddMapping">取消</button>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showTplModal = false">取消</button>
            <button class="btn btn-primary" :disabled="tplSaving" @click="saveTpl">
              <span v-if="tplSaving" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-floppy me-1"></i>儲存模板
            </button>
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
