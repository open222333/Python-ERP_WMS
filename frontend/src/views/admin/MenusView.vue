<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

// ── 商品 / 倉庫（庫存聯動用）─────────────────────────
interface SimpleProduct   { _id: string; name: string; sku: string }
interface SimpleWarehouse { _id: string; name: string }
const products   = ref<SimpleProduct[]>([])
const warehouses = ref<SimpleWarehouse[]>([])
async function loadProductsAndWarehouses() {
  try {
    const [pRes, wRes] = await Promise.all([
      http.get('/product/'),
      http.get('/warehouse/'),
    ])
    products.value   = (pRes.data.data   || []).filter((p: any) => p.status === 1)
    warehouses.value = wRes.data.data    || []
  } catch { /* 非關鍵，靜默失敗 */ }
}

// ── Interfaces ─────────────────────────────────────────
interface MenuCat {
  _id: string
  name: string
  sort_order: number
  status: number
}

interface OptionChoice {
  _id:         string
  name:        string
  extra_price: number
  is_default:  boolean
}

interface OptionGroup {
  _id:      string
  name:     string
  type:     'single' | 'multiple'
  required: boolean
  choices:  OptionChoice[]
}

interface LinkedProduct {
  product_id:   string
  warehouse_id: string
  consume_qty:  number
}

interface MenuItemData {
  _id:               string
  name:              string
  category:          string
  price:             number
  description:       string
  status:            number
  sort_order:        number
  consume_inventory: boolean
  linked_products:   LinkedProduct[]
  applied_group_ids: string[]
  applied_groups:    OptionGroup[]
}

interface MenuData {
  _id:           string
  name:          string
  description:   string
  sort_order:    number
  status:        number
  categories?:   MenuCat[]
  items?:        MenuItemData[]
  option_groups?: OptionGroup[]
}

// ── State ──────────────────────────────────────────────
const menus          = ref<MenuData[]>([])
const selectedMenuId   = ref<string>('')
const selectedMenuData = ref<MenuData | null>(null)
const loading  = ref(false)
const saving   = ref(false)
const activeTab = ref<'items' | 'categories' | 'options'>('items')

// 菜單 Modal
const showMenuModal = ref(false)
const menuForm = ref({ _id: '', name: '', description: '', sort_order: 0, status: 1 })

// 品項 Modal
const showItemModal = ref(false)
const itemForm = ref<{
  _id: string; name: string; category: string; price: number; description: string;
  sort_order: number; status: number; consume_inventory: boolean;
  linked_products: LinkedProduct[];
  applied_group_ids: string[];
}>({
  _id: '', name: '', category: '', price: 0, description: '',
  sort_order: 0, status: 1, consume_inventory: false,
  linked_products: [],
  applied_group_ids: [],
})

function addLinkedProduct() {
  itemForm.value.linked_products.push({ product_id: '', warehouse_id: '', consume_qty: 1 })
}
function removeLinkedProduct(idx: number) {
  itemForm.value.linked_products.splice(idx, 1)
}

// 分類 Modal
const showCatModal = ref(false)
const catForm = ref({ _id: '', name: '', sort_order: 0, status: 1 })

// 選項組 Modal
const showOgModal = ref(false)
const ogSaving    = ref(false)
const ogForm = ref<{
  _id: string
  name: string
  type: 'single' | 'multiple'
  required: boolean
  choices: { _id: string; name: string; extra_price: number; is_default: boolean }[]
}>({
  _id: '', name: '', type: 'single', required: true, choices: [],
})

// ── API ────────────────────────────────────────────────
async function loadMenus() {
  loading.value = true
  try {
    const res = await http.get('/menu/')
    menus.value = res.data.data || []
    if (selectedMenuId.value) {
      await loadMenuDetail(selectedMenuId.value)
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

async function selectMenu(mid: string) {
  selectedMenuId.value = mid
  if (mid) {
    await loadMenuDetail(mid)
  } else {
    selectedMenuData.value = null
  }
}

// ── 菜單 CRUD ──────────────────────────────────────────
function openMenuModal(m?: MenuData) {
  if (m) {
    menuForm.value = {
      _id: m._id, name: m.name,
      description: m.description || '', sort_order: m.sort_order || 0, status: m.status ?? 1,
    }
  } else {
    menuForm.value = { _id: '', name: '', description: '', sort_order: 0, status: 1 }
  }
  showMenuModal.value = true
}

async function saveMenu() {
  if (!menuForm.value.name.trim()) { toast.show('請填寫菜單名稱', 'danger'); return }
  saving.value = true
  try {
    if (menuForm.value._id) {
      await http.put(`/menu/${menuForm.value._id}`, menuForm.value)
    } else {
      await http.post('/menu/', menuForm.value)
    }
    toast.show('儲存成功', 'success')
    showMenuModal.value = false
    await loadMenus()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function delMenu(id: string) {
  if (!confirm('確定要刪除此菜單？此操作不可逆。')) return
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
  if (item) {
    // 重新從已更新的 selectedMenuData 取得最新品項資料（若有的話）
    const fresh = selectedMenuData.value?.items?.find(i => i._id === item._id)
    const src = fresh ?? item
    itemForm.value = {
      _id: src._id, name: src.name, category: src.category || '',
      price: src.price || 0, description: src.description || '',
      sort_order: src.sort_order || 0, status: src.status ?? 1,
      consume_inventory: !!src.consume_inventory,
      linked_products: (src.linked_products || []).map(lp => ({
        product_id:   lp.product_id   || '',
        warehouse_id: lp.warehouse_id || '',
        consume_qty:  lp.consume_qty  || 1,
      })),
      applied_group_ids: [...(src.applied_group_ids || [])],
    }
  } else {
    itemForm.value = {
      _id: '', name: '', category: '', price: 0, description: '',
      sort_order: 0, status: 1, consume_inventory: false,
      linked_products: [],
      applied_group_ids: [],
    }
  }
  showItemModal.value = true
}

async function saveItem() {
  if (!itemForm.value.name.trim()) { toast.show('請填寫品項名稱', 'danger'); return }
  if (!selectedMenuId.value) { toast.show('請先選擇菜單', 'danger'); return }
  saving.value = true
  try {
    const payload = { ...itemForm.value }
    if (itemForm.value._id) {
      await http.put(`/menu/${selectedMenuId.value}/item/${itemForm.value._id}`, payload)
    } else {
      await http.post(`/menu/${selectedMenuId.value}/item`, payload)
    }
    toast.show('儲存成功', 'success')
    showItemModal.value = false
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function delItem(itemId: string) {
  if (!confirm('確定要刪除此品項？')) return
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
  catForm.value = cat
    ? { _id: cat._id, name: cat.name, sort_order: cat.sort_order ?? 0, status: cat.status ?? 1 }
    : { _id: '', name: '', sort_order: 0, status: 1 }
  showCatModal.value = true
}

async function saveCat() {
  if (!catForm.value.name.trim()) { toast.show('請填寫分類名稱', 'danger'); return }
  if (!selectedMenuId.value) return
  saving.value = true
  try {
    if (catForm.value._id) {
      await http.put(`/menu/${selectedMenuId.value}/category/${catForm.value._id}`, catForm.value)
    } else {
      await http.post(`/menu/${selectedMenuId.value}/category`, catForm.value)
    }
    toast.show('儲存成功', 'success')
    showCatModal.value = false
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function delCat(catId: string) {
  if (!confirm('確定要刪除此分類？')) return
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
  if (og) {
    ogForm.value = {
      _id:      og._id,
      name:     og.name,
      type:     og.type,
      required: og.required,
      choices:  og.choices.map(c => ({ ...c })),
    }
  } else {
    ogForm.value = { _id: '', name: '', type: 'single', required: true, choices: [] }
  }
  showOgModal.value = true
}

function addChoice() {
  ogForm.value.choices.push({ _id: '', name: '', extra_price: 0, is_default: false })
}

function removeChoice(idx: number) {
  ogForm.value.choices.splice(idx, 1)
}

function setDefault(idx: number) {
  if (ogForm.value.type === 'single') {
    // 單選：只能一個預設
    ogForm.value.choices.forEach((c, i) => { c.is_default = i === idx })
  } else {
    ogForm.value.choices[idx].is_default = !ogForm.value.choices[idx].is_default
  }
}

async function saveOg() {
  if (!ogForm.value.name.trim()) { toast.show('請填寫選項組名稱', 'danger'); return }
  if (!selectedMenuId.value) return
  ogSaving.value = true
  try {
    const payload = {
      name:     ogForm.value.name.trim(),
      type:     ogForm.value.type,
      required: ogForm.value.required,
      choices:  ogForm.value.choices
        .map(c => ({
          name:        c.name.trim(),
          extra_price: Number(c.extra_price) || 0,
          is_default:  c.is_default,
        }))
        .filter(c => c.name),
    }
    if (ogForm.value._id) {
      await http.put(`/menu/${selectedMenuId.value}/option-group/${ogForm.value._id}`, payload)
    } else {
      await http.post(`/menu/${selectedMenuId.value}/option-group`, payload)
    }
    toast.show('儲存成功', 'success')
    showOgModal.value = false
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    ogSaving.value = false
  }
}

async function delOg(gid: string) {
  if (!confirm('確定要刪除此選項組？已套用的品項也將移除關聯。')) return
  try {
    await http.delete(`/menu/${selectedMenuId.value}/option-group/${gid}`)
    toast.show('已刪除', 'success')
    await loadMenuDetail(selectedMenuId.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

onMounted(() => { loadMenus(); loadProductsAndWarehouses() })
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
          <table class="table mb-0">
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
              <tr
                v-for="m in menus" :key="m._id"
                :class="{ 'table-active': selectedMenuId === m._id }"
                style="cursor: pointer"
                @click="selectMenu(m._id)"
              >
                <td class="fw-semibold">{{ m.name }}</td>
                <td class="text-muted small">{{ m.items?.length ?? 0 }}</td>
                <td>
                  <span :class="m.status === 1 ? 'badge bg-success' : 'badge bg-secondary'">
                    {{ m.status === 1 ? '啟用' : '停用' }}
                  </span>
                </td>
                <td>
                  <div class="d-flex gap-1">
                    <button class="btn btn-xs btn-outline-primary" @click.stop="openMenuModal(m)">
                      <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-xs btn-outline-danger" @click.stop="delMenu(m._id)">
                      <i class="bi bi-trash"></i>
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
      <div class="table-card h-100">
        <div class="table-header">
          <div>
            <span class="fw-semibold" style="font-size:.93rem">
              <i class="bi bi-menu-button-wide me-1 text-primary"></i>
              <span v-if="selectedMenuData" class="fw-bold">{{ selectedMenuData.name }}</span>
              <span v-else class="text-muted fw-normal small">— 請先從左側選擇菜單</span>
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
            <button v-if="activeTab === 'categories'" class="btn btn-sm btn-outline-secondary" @click="openCatModal()"><i class="bi bi-plus-lg"></i> 新增分類</button>
            <button v-if="activeTab === 'options'"    class="btn btn-sm btn-outline-secondary" @click="openOgModal()"><i class="bi bi-plus-lg"></i> 新增選項組</button>
          </div>
        </div>

        <!-- ── 品項 Tab ── -->
        <div v-if="activeTab === 'items'">
          <div class="table-responsive">
            <table class="table mb-0 table-sm">
              <thead>
                <tr>
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
                  <td colspan="7" class="text-center text-muted py-3">請從左側選擇菜單</td>
                </tr>
                <tr v-else-if="!selectedMenuData?.items?.length">
                  <td colspan="7" class="text-center text-muted py-3">此菜單尚無品項</td>
                </tr>
                <tr v-for="item in selectedMenuData?.items" :key="item._id">
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
                    <span v-else class="badge bg-light text-secondary">不扣</span>
                  </td>
                  <td>
                    <span :class="item.status === 1 ? 'badge bg-success' : 'badge bg-secondary'">
                      {{ item.status === 1 ? '啟用' : '停用' }}
                    </span>
                  </td>
                  <td>
                    <div class="d-flex gap-1">
                      <button class="btn btn-xs btn-outline-primary"  @click="openItemModal(item)"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delItem(item._id)"><i class="bi bi-trash"></i></button>
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
            <table class="table mb-0 table-sm">
              <thead>
                <tr><th>名稱</th><th>排序</th><th>狀態</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-if="!selectedMenuId">
                  <td colspan="4" class="text-center text-muted py-3">請從左側選擇菜單</td>
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
                      <button class="btn btn-xs btn-outline-primary"  @click="openCatModal(cat)"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delCat(cat._id)"><i class="bi bi-trash"></i></button>
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
            <table class="table mb-0 table-sm">
              <thead>
                <tr><th>選項組名稱</th><th>類型</th><th>必選</th><th>選項數</th><th>套用品項數</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-if="!selectedMenuId">
                  <td colspan="6" class="text-center text-muted py-3">請從左側選擇菜單</td>
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
                      <button class="btn btn-xs btn-outline-primary"  @click="openOgModal(og)"><i class="bi bi-pencil"></i></button>
                      <button class="btn btn-xs btn-outline-danger"   @click="delOg(og._id)"><i class="bi bi-trash"></i></button>
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
    <div v-if="showMenuModal" class="modal fade show d-block" style="background:rgba(0,0,0,.5)" @click.self="showMenuModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ menuForm._id ? '編輯菜單' : '新增菜單' }}</h5>
            <button type="button" class="btn-close" @click="showMenuModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">名稱 <span class="text-danger">*</span></label>
              <input v-model="menuForm.name" type="text" class="form-control" placeholder="例：午餐菜單" />
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">描述</label>
              <input v-model="menuForm.description" type="text" class="form-control" placeholder="選填" />
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

    <!-- 品項 Modal -->
    <div v-if="showItemModal" class="modal fade show d-block" style="background:rgba(0,0,0,.5)" @click.self="showItemModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ itemForm._id ? '編輯品項' : '新增品項' }}</h5>
            <button type="button" class="btn-close" @click="showItemModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-md-8">
                <label class="form-label fw-semibold">品項名稱 <span class="text-danger">*</span></label>
                <input v-model="itemForm.name" type="text" class="form-control" placeholder="例：招牌炒飯" />
              </div>
              <div class="col-md-4">
                <label class="form-label fw-semibold">售價 <span class="text-danger">*</span></label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input v-model.number="itemForm.price" type="number" class="form-control" min="0" step="1" />
                </div>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">分類</label>
                <input v-model="itemForm.category" type="text" class="form-control"
                       :list="`cat-list-${selectedMenuId}`" placeholder="選擇或輸入分類" />
                <datalist :id="`cat-list-${selectedMenuId}`">
                  <option v-for="c in selectedMenuData?.categories" :key="c._id" :value="c.name" />
                </datalist>
              </div>
              <div class="col-md-3">
                <label class="form-label fw-semibold">排序</label>
                <input v-model.number="itemForm.sort_order" type="number" class="form-control" min="0" />
              </div>
              <div class="col-md-3">
                <label class="form-label fw-semibold">狀態</label>
                <select v-model.number="itemForm.status" class="form-select">
                  <option :value="1">啟用</option>
                  <option :value="0">停用</option>
                </select>
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold">描述</label>
                <input v-model="itemForm.description" type="text" class="form-control" placeholder="選填" />
              </div>
              <div class="col-12">
                <div class="form-check form-switch">
                  <input v-model="itemForm.consume_inventory" class="form-check-input" type="checkbox" id="item-consume" />
                  <label class="form-check-label fw-semibold" for="item-consume">結帳時消耗庫存</label>
                </div>
                <div class="form-text">開啟後，POS 結帳會扣減對應商品庫存。</div>
              </div>

              <!-- 庫存聯動 -->
              <div class="col-12" v-if="itemForm.consume_inventory">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <label class="form-label fw-semibold mb-0">
                    <i class="bi bi-link-45deg me-1 text-primary"></i>庫存聯動商品
                  </label>
                  <button type="button" class="btn btn-sm btn-outline-primary" @click="addLinkedProduct">
                    <i class="bi bi-plus"></i> 新增
                  </button>
                </div>
                <div v-if="!itemForm.linked_products.length" class="text-muted small fst-italic mb-1">
                  尚未設定聯動商品，結帳時不會扣庫存。
                </div>
                <div v-for="(lp, idx) in itemForm.linked_products" :key="idx"
                     class="linked-row d-flex align-items-center gap-2 mb-2">
                  <select v-model="lp.product_id" class="form-select form-select-sm">
                    <option value="">-- 選擇商品 --</option>
                    <option v-for="p in products" :key="p._id" :value="p._id">
                      {{ p.name }}{{ p.sku ? ` (${p.sku})` : '' }}
                    </option>
                  </select>
                  <select v-model="lp.warehouse_id" class="form-select form-select-sm">
                    <option value="">預設倉庫</option>
                    <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
                  </select>
                  <input v-model.number="lp.consume_qty" type="number" min="1"
                         class="form-control form-control-sm lp-qty" placeholder="扣量" />
                  <button type="button" class="btn btn-sm btn-outline-danger flex-shrink-0"
                          @click="removeLinkedProduct(idx)">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
                <div class="form-text">每賣出 1 份，依上方設定各扣減指定商品庫存數量。</div>
              </div>
              <!-- 套用客製化選項組 -->
              <div class="col-12" v-if="selectedMenuData?.option_groups?.length">
                <label class="form-label fw-semibold"><i class="bi bi-sliders2 me-1"></i>客製化選項組</label>
                <div class="d-flex flex-wrap gap-3">
                  <div v-for="og in selectedMenuData?.option_groups" :key="og._id" class="form-check">
                    <input type="checkbox" :id="`og-cb-${og._id}`" class="form-check-input"
                           :value="og._id" v-model="itemForm.applied_group_ids" />
                    <label :for="`og-cb-${og._id}`" class="form-check-label">
                      {{ og.name }}
                      <span class="text-muted small">（{{ og.choices?.length || 0 }} 選項）</span>
                    </label>
                  </div>
                </div>
                <div class="form-text">勾選後，POS 點此品項時會彈出選項讓顧客選擇。</div>
              </div>
              <div class="col-12" v-else-if="selectedMenuId">
                <div class="text-muted small fst-italic">
                  <i class="bi bi-info-circle me-1"></i>此菜單尚無客製化選項組，可至「客製化」tab 新增。
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showItemModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveItem">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分類 Modal -->
    <div v-if="showCatModal" class="modal fade show d-block" style="background:rgba(0,0,0,.5)" @click.self="showCatModal = false">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ catForm._id ? '編輯分類' : '新增分類' }}</h5>
            <button type="button" class="btn-close" @click="showCatModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">分類名稱 <span class="text-danger">*</span></label>
              <input v-model="catForm.name" type="text" class="form-control" placeholder="例：主食" />
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

    <!-- 選項組 Modal -->
    <div v-if="showOgModal" class="modal fade show d-block" style="background:rgba(0,0,0,.5)" @click.self="showOgModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-sliders2 me-1"></i>{{ ogForm._id ? '編輯選項組' : '新增選項組' }}
            </h5>
            <button type="button" class="btn-close" @click="showOgModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3 mb-3">
              <div class="col-md-5">
                <label class="form-label fw-semibold">選項組名稱 <span class="text-danger">*</span></label>
                <input v-model="ogForm.name" type="text" class="form-control" placeholder="例：辣度、甜度" />
              </div>
              <div class="col-md-4">
                <label class="form-label fw-semibold">選擇類型</label>
                <select v-model="ogForm.type" class="form-select">
                  <option value="single">單選（只能選一個）</option>
                  <option value="multiple">多選（可選多個）</option>
                </select>
              </div>
              <div class="col-md-3 d-flex align-items-end">
                <div class="form-check form-switch mb-0 pb-2">
                  <input v-model="ogForm.required" class="form-check-input" type="checkbox" id="og-required" />
                  <label class="form-check-label fw-semibold" for="og-required">必選</label>
                </div>
              </div>
            </div>

            <!-- 選項清單 -->
            <div class="d-flex align-items-center justify-content-between mb-2">
              <label class="form-label fw-semibold mb-0">選項清單</label>
              <button class="btn btn-sm btn-outline-primary" type="button" @click="addChoice">
                <i class="bi bi-plus-lg"></i> 新增選項
              </button>
            </div>
            <div v-if="!ogForm.choices.length" class="text-muted small fst-italic mb-2">
              尚無選項，點右上角新增
            </div>
            <div class="og-choice-list">
              <div v-for="(ch, idx) in ogForm.choices" :key="idx" class="og-choice-row">
                <div class="flex-grow-1">
                  <input v-model="ch.name" type="text" class="form-control form-control-sm"
                         placeholder="選項名稱（例：不辣）" />
                </div>
                <div style="width:110px">
                  <div class="input-group input-group-sm">
                    <span class="input-group-text">+$</span>
                    <input v-model.number="ch.extra_price" type="number" class="form-control" min="0" step="1" placeholder="0" />
                  </div>
                </div>
                <div>
                  <button type="button"
                    class="btn btn-sm"
                    :class="ch.is_default ? 'btn-warning' : 'btn-outline-secondary'"
                    @click="setDefault(idx)"
                    :title="ogForm.type === 'single' ? '設為預設' : '切換預設'"
                  >
                    <i class="bi" :class="ch.is_default ? 'bi-star-fill' : 'bi-star'"></i>
                  </button>
                </div>
                <div>
                  <button type="button" class="btn btn-sm btn-outline-danger" @click="removeChoice(idx)">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="form-text mt-1">
              <i class="bi bi-star-fill text-warning me-1"></i>金色星號 = POS 預設勾選；加價 0 = 不另加收費
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showOgModal = false">取消</button>
            <button class="btn btn-primary" :disabled="ogSaving" @click="saveOg">
              <span v-if="ogSaving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>

  </Teleport>
</template>

<style scoped>
.btn-xs {
  padding: .15rem .4rem;
  font-size: .75rem;
}
.bg-indigo {
  background-color: #6366f1;
  color: #fff;
}

/* 選項組 Modal 選項列 */
.og-choice-list { display: flex; flex-direction: column; gap: 8px; }
.og-choice-row  { display: flex; align-items: center; gap: 8px; }

/* 庫存聯動列 */
.linked-row .form-select:first-child { flex: 2; min-width: 0; }
.linked-row .form-select:nth-child(2) { flex: 1.5; min-width: 0; }
.lp-qty { width: 70px; flex-shrink: 0; text-align: center; }
</style>
