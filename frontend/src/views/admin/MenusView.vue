<script setup lang="ts">
import { useFieldErrors } from '@/composables/useFieldErrors'
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import http from '@/api'
import { fetchAllPages } from '@/api/paging'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import type { Store } from '@/types'
import { appConfirm } from '@/composables/useConfirm'
// [U10] 2026-11 拆分：品項、選項組、批次客製化三個彈窗移至 components/menus/（型別在 types.ts）
import type { SimpleProduct, SimpleWarehouse, MenuCat, OptionGroup, MenuItemData, MenuData } from '@/components/menus/types'
import MenuItemModal from '@/components/menus/MenuItemModal.vue'
import OptionGroupModal from '@/components/menus/OptionGroupModal.vue'
import BatchCustomizeModal from '@/components/menus/BatchCustomizeModal.vue'

const toast = useToastStore()
const fe    = useFieldErrors()   // [U9] 菜單／分類表單共用（同時只開一個彈窗）
const auth  = useAuthStore()

// ── 商品 / 倉庫（庫存聯動用）─────────────────────────
const products   = ref<SimpleProduct[]>([])
const warehouses = ref<SimpleWarehouse[]>([])
async function loadProductsAndWarehouses() {
  try {
    const [pList, wRes] = await Promise.all([
      fetchAllPages('/product/', { status: 1 }),   // [U3] 原本只拿到前 200 筆，連結商品選單會缺
      http.get('/warehouse/'),
    ])
    products.value   = pList.filter((p: any) => p.status === 1)
    warehouses.value = wRes.data.data    || []
  } catch { /* 非關鍵，靜默失敗 */ }
}

// ── Stores ─────────────────────────────────────────────
const stores   = ref<Store[]>([])
const storeMap = computed(() => Object.fromEntries(stores.value.map(s => [s._id, s.name])))

// ── State ──────────────────────────────────────────────
const menus          = ref<MenuData[]>([])
const selectedMenuId   = ref<string>('')
const selectedMenuData = ref<MenuData | null>(null)
const loading  = ref(false)
const saving   = ref(false)
const activeTab = ref<'items' | 'categories' | 'options'>('items')
const importing = ref(false)
const importFileRef = ref<HTMLInputElement>()

// 預設菜單（localStorage 記憶，進頁面自動展開）
const defaultMenuId = ref(localStorage.getItem('admin_default_menu_id') || '')

function setDefaultMenu(id: string) {
  if (defaultMenuId.value === id) {
    defaultMenuId.value = ''
    localStorage.removeItem('admin_default_menu_id')
    toast.show('已取消預設菜單')
  } else {
    defaultMenuId.value = id
    localStorage.setItem('admin_default_menu_id', id)
    toast.show('已設為預設菜單', 'success')
  }
}

// ── 批次編輯 ────────────────────────────────────────────
const selectedItemIds  = ref<string[]>([])
const selectAllRef     = ref<HTMLInputElement>()

const allItemsSelected = computed(() => {
  const items = selectedMenuData.value?.items || []
  return items.length > 0 && selectedItemIds.value.length === items.length
})

const someItemsSelected = computed(() =>
  selectedItemIds.value.length > 0 && !allItemsSelected.value
)

// [OPT] 移除 deep watch：indeterminate 只依賴兩集合的數量。
//       selectedItemIds 以 push/splice 就地變動，淺層 watch ref 不會觸發 → 改 watch length；
//       selectedMenuData 每次都整體重新賦值，items 用淺層 getter 即可偵測切換/重載
watch([() => selectedItemIds.value.length, () => selectedMenuData.value?.items], async () => {
  await nextTick()
  if (selectAllRef.value) selectAllRef.value.indeterminate = someItemsSelected.value
})

// 菜單 Modal
const showMenuModal = ref(false)
const menuForm = ref({ _id: '', name: '', description: '', sort_order: 0, status: 1, store_id: '' })

// 品項／選項組／批次彈窗（子元件，以 ref 呼叫 open()）
const itemModal  = ref<InstanceType<typeof MenuItemModal> | null>(null)
const ogModal    = ref<InstanceType<typeof OptionGroupModal> | null>(null)
const batchModal = ref<InstanceType<typeof BatchCustomizeModal> | null>(null)

// 分類 Modal
const showCatModal = ref(false)
const catForm = ref({ _id: '', name: '', sort_order: 0, status: 1 })

// ── API ────────────────────────────────────────────────
async function loadMenus() {
  loading.value = true
  try {
    const [mRes, sRes] = await Promise.all([
      http.get('/menu/'),
      auth.isAdmin ? http.get('/store/') : Promise.resolve({ data: { data: [] } }),
    ])
    menus.value  = mRes.data.data || []
    stores.value = sRes.data.data || []
    if (selectedMenuId.value) {
      // 確認菜單仍存在（避免被刪後報錯）
      if (menus.value.find(m => m._id === selectedMenuId.value)) {
        await loadMenuDetail(selectedMenuId.value)
      } else {
        selectedMenuId.value   = ''
        selectedMenuData.value = null
      }
    }
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function loadMenuDetail(mid: string) {
  try {
    const res = await http.get(`/menu/${mid}`)
    selectedMenuData.value = res.data.data || null
  } catch {
    toast.show('載入菜單詳情失敗', 'danger')
  }
}

// [U13] 手機／平板上菜單列表與品項面板上下排列，點選菜單後自動捲到品項面板
const detailPanel = ref<HTMLElement | null>(null)

async function selectMenu(mid: string, scroll = false) {
  selectedMenuId.value = mid
  selectedItemIds.value = []
  if (mid) {
    await loadMenuDetail(mid)
    if (scroll && window.matchMedia('(max-width: 991.98px)').matches) {
      await nextTick()
      detailPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } else {
    selectedMenuData.value = null
  }
}

// ── 菜單 CRUD ──────────────────────────────────────────
function openMenuModal(m?: MenuData) {
  fe.clear()
  if (m) {
    menuForm.value = {
      _id: m._id, name: m.name,
      description: m.description || '', sort_order: m.sort_order || 0, status: m.status ?? 1,
      store_id: m.store_id ?? '',
    }
  } else if (menuForm.value._id) {
    menuForm.value = { _id: '', name: '', description: '', sort_order: 0, status: 1, store_id: '' }
  }
  showMenuModal.value = true
}

async function saveMenu() {
  if (!fe.check({ menu_name: [!menuForm.value.name.trim(), '請填寫菜單名稱'] })) return
  saving.value = true
  const isNew = !menuForm.value._id
  try {
    if (menuForm.value._id) {
      await http.put(`/menu/${menuForm.value._id}`, menuForm.value)
    } else {
      const payload: Record<string, any> = { ...menuForm.value }
      if (!payload.store_id) delete payload.store_id
      await http.post('/menu/', payload)
    }
    toast.show('儲存成功', 'success')
    showMenuModal.value = false
    if (isNew) menuForm.value = { _id: '', name: '', description: '', sort_order: 0, status: 1, store_id: '' }
    await loadMenus()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function delMenu(id: string) {
  if (!(await appConfirm('確定要刪除此菜單？此操作不可逆。', { danger: true }))) return
  try {
    await http.delete(`/menu/${id}`)
    toast.show('已刪除', 'success')
    if (selectedMenuId.value === id) {
      selectedMenuId.value   = ''
      selectedMenuData.value = null
    }
    await loadMenus()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── 品項 CRUD ──────────────────────────────────────────
async function openItemModal(item?: MenuItemData) {
  // 每次開啟前刷新菜單詳情，確保選項組資料是最新的
  if (selectedMenuId.value) {
    await loadMenuDetail(selectedMenuId.value)
  }
  itemModal.value?.open(item)
}

async function delItem(itemId: string) {
  if (!(await appConfirm('確定要刪除此品項？', { danger: true }))) return
  try {
    await http.delete(`/menu/${selectedMenuId.value}/item/${itemId}`)
    toast.show('已刪除', 'success')
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── 分類 CRUD ──────────────────────────────────────────
function openCatModal(cat?: MenuCat) {
  fe.clear()
  if (cat) {
    catForm.value = { _id: cat._id, name: cat.name, sort_order: cat.sort_order ?? 0, status: cat.status ?? 1 }
  } else if (catForm.value._id) {
    catForm.value = { _id: '', name: '', sort_order: 0, status: 1 }
  }
  showCatModal.value = true
}

async function saveCat() {
  if (!fe.check({ cat_name: [!catForm.value.name.trim(), '請填寫分類名稱'] })) return
  if (!selectedMenuId.value) return
  saving.value = true
  const isNew = !catForm.value._id
  try {
    if (catForm.value._id) {
      await http.put(`/menu/${selectedMenuId.value}/category/${catForm.value._id}`, catForm.value)
    } else {
      await http.post(`/menu/${selectedMenuId.value}/category`, catForm.value)
    }
    toast.show('儲存成功', 'success')
    showCatModal.value = false
    if (isNew) catForm.value = { _id: '', name: '', sort_order: 0, status: 1 }
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function delCat(catId: string) {
  if (!(await appConfirm('確定要刪除此分類？', { danger: true }))) return
  try {
    await http.delete(`/menu/${selectedMenuId.value}/category/${catId}`)
    toast.show('已刪除', 'success')
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── 選項組 CRUD ────────────────────────────────────────
function openOgModal(og?: OptionGroup) {
  ogModal.value?.open(og)
}

async function delOg(gid: string) {
  if (!(await appConfirm('確定要刪除此選項組？已套用的品項也將移除關聯。', { danger: true }))) return
  try {
    await http.delete(`/menu/${selectedMenuId.value}/option-group/${gid}`)
    toast.show('已刪除', 'success')
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── 批次編輯函式 ─────────────────────────────────────────
function toggleItemSelect(itemId: string) {
  const idx = selectedItemIds.value.indexOf(itemId)
  if (idx >= 0) selectedItemIds.value.splice(idx, 1)
  else selectedItemIds.value.push(itemId)
}

function toggleAllItems() {
  const items = selectedMenuData.value?.items || []
  selectedItemIds.value = selectedItemIds.value.length === items.length
    ? []
    : items.map(i => i._id)
}

function openBatchModal() {
  batchModal.value?.open()
}

async function onBatchSaved() {
  selectedItemIds.value = []
  await loadMenuDetail(selectedMenuId.value)
}

// ── 匯出 / 匯入 ─────────────────────────────────────────
async function exportMenu() {
  if (!selectedMenuId.value) return
  try {
    const res = await http.get(`/menu/${selectedMenuId.value}/export`, { responseType: 'blob' })
    const cd  = res.headers['content-disposition'] || ''
    const match = cd.match(/filename\*?=(?:UTF-8'')?([^;\r\n]+)/i)
    const filename = match ? decodeURIComponent(match[1].replace(/['"]/g, '')) : 'menu.json'
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '匯出失敗', 'danger')
  }
}

function triggerImport() {
  importFileRef.value?.click()
}

async function onImportFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !selectedMenuId.value) return
  importing.value = true
  try {
    const text = await file.text()
    const json = JSON.parse(text)
    const res  = await http.post(`/menu/${selectedMenuId.value}/import`, json)
    const d    = res.data
    toast.show(
      `匯入完成：分類 ${d.categories_created ?? 0} 筆、品項 ${d.items_created ?? 0} 新增 / ${d.items_updated ?? 0} 更新`,
      'success'
    )
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '匯入失敗', 'danger')
  } finally {
    importing.value = false
    if (importFileRef.value) importFileRef.value.value = ''
  }
}

onMounted(() => {
  // 預設菜單：進頁面前先設定 selectedMenuId，讓 loadMenus 自動展開
  if (defaultMenuId.value) selectedMenuId.value = defaultMenuId.value
  loadMenus()
  loadProductsAndWarehouses()
})
</script>

<template>
  <div class="row g-3">
    <!-- 左：菜單列表 -->
    <div class="col-12 col-lg-4">
      <div class="table-card h-100">
        <div class="table-header">
          <h6><i class="bi bi-menu-button-wide me-1"></i>菜單列表</h6>
          <button class="btn btn-sm btn-primary" @click="openMenuModal()">
            <i class="bi bi-plus-lg"></i> 新增菜單
          </button>
        </div>
        <div class="table-responsive">
          <table v-stack-table class="table mb-0">
            <thead>
              <tr>
                <th>名稱</th>
                <th>品項數</th>
                <th>狀態</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="4" class="text-center py-3">
                  <div class="spinner-border spinner-border-sm"></div>
                </td>
              </tr>
              <tr v-else-if="!menus.length">
                <td colspan="4" class="text-center text-muted py-3">無菜單</td>
              </tr>
              <tr class="cursor-pointer"
                v-for="m in menus" :key="m._id"
                :class="{ 'table-active': selectedMenuId === m._id }"
                @click="selectMenu(m._id, true)">
                <td class="fw-semibold">
                  {{ m.name }}
                  <span v-if="defaultMenuId === m._id" class="badge bg-warning text-dark ms-1 fz-65">預設</span>
                  <span v-if="m.store_id && storeMap[m.store_id]" class="badge bg-info text-dark ms-1 fz-65">{{ storeMap[m.store_id] }}</span>
                </td>
                <td class="text-muted small">{{ m.items?.length ?? 0 }}</td>
                <td>
                  <span :class="m.status === 1 ? 'badge bg-success' : 'badge bg-secondary'">
                    {{ m.status === 1 ? '啟用' : '停用' }}
                  </span>
                </td>
                <td>
                  <div class="d-flex gap-1">
                    <button class="btn btn-xs btn-outline-primary" @click.stop="openMenuModal(m)" aria-label="編輯" title="編輯">
                      <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-xs btn-outline-danger" @click.stop="delMenu(m._id)" aria-label="刪除" title="刪除">
                      <i class="bi bi-trash"></i>
                    </button>
                    <button
                      class="btn btn-xs"
                      :class="defaultMenuId === m._id ? 'btn-warning' : 'btn-outline-secondary'"
                      :title="defaultMenuId === m._id ? '取消預設菜單' : '設為預設菜單（進入頁面自動展開）'"
                      @click.stop="setDefaultMenu(m._id)"
                    >
                      <i class="bi" :class="defaultMenuId === m._id ? 'bi-star-fill' : 'bi-star'"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 右：品項 / 分類 / 客製化面板 -->
    <div class="col-12 col-lg-8">
      <div ref="detailPanel" class="table-card h-100 menu-detail-panel">
        <div class="table-header">
          <div>
            <span class="fw-semibold fz-93">
              <i class="bi bi-menu-button-wide me-1 text-primary"></i>
              <span v-if="selectedMenuData" class="fw-bold">{{ selectedMenuData.name }}</span>
              <span v-else class="text-muted fw-normal small">— 請先選擇菜單</span>
            </span>
          </div>
          <div v-if="selectedMenuId" class="d-flex gap-2 align-items-center flex-wrap">
            <!-- Tabs -->
            <div class="btn-group btn-group-sm">
              <button class="btn"
                :class="activeTab === 'items' ? 'btn-secondary active' : 'btn-outline-secondary'"
                @click="activeTab = 'items'">
                <i class="bi bi-list-ul me-1"></i>品項
              </button>
              <button class="btn"
                :class="activeTab === 'categories' ? 'btn-secondary active' : 'btn-outline-secondary'"
                @click="activeTab = 'categories'">
                <i class="bi bi-tags me-1"></i>分類
              </button>
              <button class="btn"
                :class="activeTab === 'options' ? 'btn-secondary active' : 'btn-outline-secondary'"
                @click="activeTab = 'options'">
                <i class="bi bi-sliders2 me-1"></i>客製化
              </button>
            </div>
            <!-- 各 tab 的新增按鈕 -->
            <button v-if="activeTab === 'items'"      class="btn btn-sm btn-primary"          @click="openItemModal()"><i class="bi bi-plus-lg"></i> 新增品項</button>
            <button v-if="activeTab === 'items' && selectedItemIds.length"
                    class="btn btn-sm btn-outline-indigo" @click="openBatchModal">
              <i class="bi bi-sliders2 me-1"></i>批次客製化
              <span class="badge bg-indigo ms-1">{{ selectedItemIds.length }}</span>
            </button>
            <button v-if="activeTab === 'categories'" class="btn btn-sm btn-outline-secondary" @click="openCatModal()"><i class="bi bi-plus-lg"></i> 新增分類</button>
            <button v-if="activeTab === 'options'"    class="btn btn-sm btn-outline-secondary" @click="openOgModal()"><i class="bi bi-plus-lg"></i> 新增選項組</button>
            <!-- 匯出 / 匯入 -->
            <div class="btn-group btn-group-sm ms-1">
              <button class="btn btn-outline-secondary" title="匯出菜單 JSON" @click="exportMenu">
                <i class="bi bi-box-arrow-up me-1"></i>匯出
              </button>
              <button class="btn btn-outline-secondary" title="從 JSON 匯入分類與品項" :disabled="importing" @click="triggerImport">
                <span v-if="importing" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-box-arrow-in-down me-1"></i>匯入
              </button>
            </div>
            <input ref="importFileRef" type="file" accept=".json,application/json" class="d-none" @change="onImportFile" />
          </div>
        </div>

        <!-- ── 品項 Tab ── -->
        <div v-if="activeTab === 'items'">
          <div class="table-responsive">
            <table v-stack-table class="table mb-0 table-sm">
              <thead>
                <tr>
                  <th class="wpx-36">
                    <input ref="selectAllRef" type="checkbox" class="form-check-input"
                           :checked="allItemsSelected" @change="toggleAllItems" />
                  </th>
                  <th>名稱</th>
                  <th>分類</th>
                  <th class="text-end">售價</th>
                  <th>客製化</th>
                  <th>庫存</th>
                  <th>狀態</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!selectedMenuId">
                  <td colspan="8" class="text-center text-muted py-3">請先選擇菜單</td>
                </tr>
                <tr v-else-if="!selectedMenuData?.items?.length">
                  <td colspan="8" class="text-center text-muted py-3">此菜單尚無品項</td>
                </tr>
                <tr v-for="item in selectedMenuData?.items" :key="item._id"
                    :class="{ 'table-active': selectedItemIds.includes(item._id) }">
                  <td>
                    <input type="checkbox" class="form-check-input"
                           :checked="selectedItemIds.includes(item._id)"
                           @change="toggleItemSelect(item._id)" />
                  </td>
                  <td class="fw-semibold">{{ item.name }}</td>
                  <td class="small text-muted">{{ item.category || '—' }}</td>
                  <td class="text-end">${{ Number(item.price || 0).toLocaleString() }}</td>
                  <td>
                    <span v-if="item.applied_group_ids?.length" class="badge bg-indigo">
                      <i class="bi bi-sliders2 me-1"></i>{{ item.applied_group_ids.length }} 組
                    </span>
                    <span v-else class="text-muted small">—</span>
                  </td>
                  <td>
                    <span v-if="item.consume_inventory" class="badge bg-info text-dark">扣庫存</span>
                    <span v-else class="badge bg-body-secondary text-secondary">不扣</span>
                  </td>
                  <td>
                    <span :class="item.status === 1 ? 'badge bg-success' : 'badge bg-secondary'">
                      {{ item.status === 1 ? '啟用' : '停用' }}
                    </span>
                  </td>
                  <td>
                    <div class="d-flex gap-1">
                      <button class="btn btn-xs btn-outline-primary"  @click="openItemModal(item)" aria-label="編輯" title="編輯"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delItem(item._id)" aria-label="刪除" title="刪除"><i class="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ── 分類 Tab ── -->
        <div v-if="activeTab === 'categories'">
          <div class="table-responsive">
            <table v-stack-table class="table mb-0 table-sm">
              <thead>
                <tr><th>名稱</th><th>排序</th><th>狀態</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-if="!selectedMenuId">
                  <td colspan="4" class="text-center text-muted py-3">請先選擇菜單</td>
                </tr>
                <tr v-else-if="!selectedMenuData?.categories?.length">
                  <td colspan="4" class="text-center text-muted py-3">此菜單尚無分類</td>
                </tr>
                <tr v-for="cat in selectedMenuData?.categories" :key="cat._id">
                  <td class="fw-semibold">{{ cat.name }}</td>
                  <td class="small text-muted">{{ cat.sort_order ?? 0 }}</td>
                  <td>
                    <span :class="cat.status === 1 ? 'badge bg-success' : 'badge bg-secondary'">
                      {{ cat.status === 1 ? '啟用' : '停用' }}
                    </span>
                  </td>
                  <td>
                    <div class="d-flex gap-1">
                      <button class="btn btn-xs btn-outline-primary"  @click="openCatModal(cat)" aria-label="編輯" title="編輯"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delCat(cat._id)" aria-label="刪除" title="刪除"><i class="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ── 客製化選項組 Tab ── -->
        <div v-if="activeTab === 'options'">
          <div class="table-responsive">
            <table v-stack-table class="table mb-0 table-sm">
              <thead>
                <tr><th>選項組名稱</th><th>類型</th><th>必選</th><th>選項數</th><th>套用品項數</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-if="!selectedMenuId">
                  <td colspan="6" class="text-center text-muted py-3">請先選擇菜單</td>
                </tr>
                <tr v-else-if="!selectedMenuData?.option_groups?.length">
                  <td colspan="6" class="text-center text-muted py-3">尚無客製化選項組，點右上角「新增選項組」</td>
                </tr>
                <tr v-for="og in selectedMenuData?.option_groups" :key="og._id">
                  <td class="fw-semibold">{{ og.name }}</td>
                  <td>
                    <span :class="og.type === 'single' ? 'badge bg-primary' : 'badge bg-secondary'">
                      {{ og.type === 'single' ? '單選' : '多選' }}
                    </span>
                  </td>
                  <td>
                    <span v-if="og.required" class="badge bg-danger">必選</span>
                    <span v-else class="text-muted small">否</span>
                  </td>
                  <td class="text-muted small">
                    {{ og.choices?.length || 0 }} 個
                    <span class="text-muted">
                      （{{ (og.choices || []).map(c => c.name).join('、') }}）
                    </span>
                  </td>
                  <td class="text-muted small">
                    {{ selectedMenuData?.items?.filter(i => i.applied_group_ids?.includes(og._id)).length || 0 }} 項
                  </td>
                  <td>
                    <div class="d-flex gap-1">
                      <button class="btn btn-xs btn-outline-primary"  @click="openOgModal(og)" aria-label="編輯" title="編輯"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delOg(og._id)" aria-label="刪除" title="刪除"><i class="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Modals ──────────────────────────────────────── -->
  <Teleport to="body">

    <!-- 菜單 Modal -->
    <div v-if="showMenuModal" class="modal fade show d-block bg-dim-50" @click.self="showMenuModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ menuForm._id ? '編輯菜單' : '新增菜單' }}</h5>
            <button type="button" class="btn-close" @click="showMenuModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">名稱 <span class="text-danger">*</span></label>
              <input v-model="menuForm.name" type="text" class="form-control" placeholder="例：午餐菜單"
                     data-field="menu_name" :class="{ 'is-invalid': fe.errors.menu_name }"
                     @input="fe.clear('menu_name')" />
              <div class="invalid-feedback">{{ fe.errors.menu_name }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">描述</label>
              <input v-model="menuForm.description" type="text" class="form-control" placeholder="選填" />
            </div>
            <div v-if="!menuForm._id && auth.isAdmin && stores.length" class="mb-3">
              <label class="form-label fw-semibold">綁定店家</label>
              <select v-model="menuForm.store_id" class="form-select">
                <option value="">— 不綁定店家 —</option>
                <option v-for="s in stores" :key="s._id" :value="s._id">{{ s.name }}（{{ s.code }}）</option>
              </select>
            </div>
            <div class="row g-3">
              <div class="col-6">
                <label class="form-label fw-semibold">排序</label>
                <input v-model.number="menuForm.sort_order" type="number" class="form-control" min="0" />
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">狀態</label>
                <select v-model.number="menuForm.status" class="form-select">
                  <option :value="1">啟用</option>
                  <option :value="0">停用</option>
                </select>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showMenuModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveMenu">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分類 Modal -->
    <div v-if="showCatModal" class="modal fade show d-block bg-dim-50" @click.self="showCatModal = false">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ catForm._id ? '編輯分類' : '新增分類' }}</h5>
            <button type="button" class="btn-close" @click="showCatModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">分類名稱 <span class="text-danger">*</span></label>
              <input v-model="catForm.name" type="text" class="form-control" placeholder="例：主食"
                     data-field="cat_name" :class="{ 'is-invalid': fe.errors.cat_name }"
                     @input="fe.clear('cat_name')" />
              <div class="invalid-feedback">{{ fe.errors.cat_name }}</div>
            </div>
            <div class="row g-3">
              <div class="col-6">
                <label class="form-label fw-semibold">排序</label>
                <input v-model.number="catForm.sort_order" type="number" class="form-control" min="0" />
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">狀態</label>
                <select v-model.number="catForm.status" class="form-select">
                  <option :value="1">啟用</option>
                  <option :value="0">停用</option>
                </select>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showCatModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveCat">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>

  </Teleport>

  <MenuItemModal ref="itemModal" :menu-id="selectedMenuId" :menu="selectedMenuData"
                 :products="products" :warehouses="warehouses" @saved="loadMenuDetail(selectedMenuId)" />
  <OptionGroupModal ref="ogModal" :menu-id="selectedMenuId" @saved="loadMenuDetail(selectedMenuId)" />
  <BatchCustomizeModal ref="batchModal" :menu-id="selectedMenuId" :menu="selectedMenuData"
                       :selected-item-ids="selectedItemIds" @saved="onBatchSaved" />
</template>

<style scoped>
.menu-detail-panel { scroll-margin-top: 64px; }   /* [U13] 捲動時避開固定頂列 */
.btn-xs {
  padding: .15rem .4rem;
  font-size: .75rem;
}
.bg-indigo {
  background-color: #6366f1;
  color: #fff;
}

/* 批次編輯按鈕 */
.btn-outline-indigo { border-color: #6366f1; color: #6366f1; background: transparent; }
.btn-outline-indigo:hover { background: #6366f1; color: #fff; }
</style>
