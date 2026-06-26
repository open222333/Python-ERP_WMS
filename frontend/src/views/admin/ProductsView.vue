<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { Category, Product } from '@/types'

const toast = useToastStore()

// ── State ──────────────────────────────────────────────────
const products   = ref<Product[]>([])
const categories = ref<Category[]>([])
const loading    = ref(false)
const saving     = ref(false)
const showModal  = ref(false)

const filterCatId = ref('')
const keyword     = ref('')

const importFileRef = ref<HTMLInputElement | null>(null)

// ── Computed ───────────────────────────────────────────────
const catMap = computed<Record<string, string>>(() =>
  Object.fromEntries(categories.value.map(c => [c._id, c.name]))
)

const filteredProducts = computed(() => {
  let list = products.value
  if (filterCatId.value) {
    list = list.filter(p => p.category_id === filterCatId.value)
  }
  if (keyword.value.trim()) {
    const kw = keyword.value.trim().toLowerCase()
    list = list.filter(p =>
      p.name.toLowerCase().includes(kw) ||
      p.sku.toLowerCase().includes(kw)
    )
  }
  return list
})

// ── Selection ──────────────────────────────────────────────
const selectedIds = ref<Set<string>>(new Set())

const allSelected = computed(() =>
  filteredProducts.value.length > 0 &&
  filteredProducts.value.every(p => selectedIds.value.has(p._id))
)
const someSelected = computed(() =>
  filteredProducts.value.some(p => selectedIds.value.has(p._id)) && !allSelected.value
)

function toggleSelectAll() {
  if (allSelected.value) {
    filteredProducts.value.forEach(p => selectedIds.value.delete(p._id))
  } else {
    filteredProducts.value.forEach(p => selectedIds.value.add(p._id))
  }
  selectedIds.value = new Set(selectedIds.value)
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function clearSelection() {
  selectedIds.value = new Set()
}

// 篩選條件變動時清除選取
watch([filterCatId, keyword], clearSelection)

// ── Batch ──────────────────────────────────────────────────
const batchCatId  = ref('')
const batchSaving = ref(false)

async function batchApply(updates: Record<string, unknown>) {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  batchSaving.value = true
  try {
    const { data } = await http.put('/product/batch', { ids, ...updates })
    toast.show(`已更新 ${data.updated} 項`, 'success')
    clearSelection()
    batchCatId.value = ''
    await loadProducts()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '批量更新失敗', 'danger')
  } finally {
    batchSaving.value = false
  }
}

async function batchDelete() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`確定刪除選取的 ${ids.length} 個產品？此操作無法復原。`)) return
  batchSaving.value = true
  try {
    const { data } = await http.delete('/product/batch', { data: { ids } })
    toast.show(`已刪除 ${data.deleted} 項`, 'success')
    clearSelection()
    await loadProducts()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '批量刪除失敗', 'danger')
  } finally {
    batchSaving.value = false
  }
}

// ── Form ───────────────────────────────────────────────────
interface ProductForm {
  _id:         string
  name:        string
  sku:         string
  barcode:     string
  category_id: string
  unit:        string
  sell_price:  number
  cost_price:  number
  min_stock:   number
  description: string
  status:      number
}

const emptyForm = (): ProductForm => ({
  _id: '', name: '', sku: genSku(), barcode: '', category_id: '',
  unit: '個', sell_price: 0, cost_price: 0, min_stock: 0,
  description: '', status: 1,
})

const form = ref<ProductForm>(emptyForm())

function genSku(): string {
  const d = new Date()
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let r = ''
  for (let i = 0; i < 4; i++) r += chars[Math.floor(Math.random() * chars.length)]
  return `SKU-${ymd}-${r}`
}

// ── API ────────────────────────────────────────────────────
async function loadCategories() {
  try {
    const { data } = await http.get('/product/category/')
    categories.value = data.data ?? data ?? []
  } catch {
    toast.show('載入分類失敗', 'danger')
  }
}

async function loadProducts() {
  loading.value = true
  try {
    const { data } = await http.get('/product/')
    products.value = data.data ?? data ?? []
  } catch {
    toast.show('載入產品失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Modal ──────────────────────────────────────────────────
function openModal(p?: Product) {
  if (p) {
    form.value = {
      _id:         p._id,
      name:        p.name,
      sku:         p.sku,
      barcode:     p.barcode ?? '',
      category_id: p.category_id ?? '',
      unit:        p.unit,
      sell_price:  p.sell_price ?? p.price ?? 0,
      cost_price:  p.cost_price ?? p.cost ?? 0,
      min_stock:   p.min_stock ?? 0,
      description: p.description ?? '',
      status:      p.status ?? 1,
    }
  } else if (form.value._id) {
    form.value = emptyForm()
  }
  showModal.value = true
}

// ── Save ───────────────────────────────────────────────────
async function save() {
  if (!form.value.name.trim() || !form.value.sku.trim()) {
    toast.show('名稱與 SKU 不得為空', 'danger')
    return
  }
  saving.value = true
  const isNew = !form.value._id
  try {
    const payload = {
      name:        form.value.name.trim(),
      sku:         form.value.sku.trim(),
      barcode:     form.value.barcode.trim(),
      category_id: form.value.category_id || null,
      unit:        form.value.unit,
      sell_price:  Number(form.value.sell_price),
      cost_price:  Number(form.value.cost_price),
      min_stock:   Number(form.value.min_stock),
      description: form.value.description,
      status:      form.value.status,
    }
    if (form.value._id) {
      await http.put(`/product/${form.value._id}`, payload)
    } else {
      await http.post('/product/', payload)
    }
    toast.show('儲存成功', 'success')
    showModal.value = false
    if (isNew) form.value = emptyForm()
    await loadProducts()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────
async function del(id: string) {
  if (!confirm('確定要刪除此產品？')) return
  try {
    await http.delete(`/product/${id}`)
    toast.show('已刪除', 'success')
    await loadProducts()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '刪除失敗', 'danger')
  }
}

// ── Import / Export ────────────────────────────────────────
async function exportProducts() {
  try {
    const { data } = await http.get('/product/export', { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'products.json'
    a.click()
    URL.revokeObjectURL(url)
    toast.show('匯出完成', 'success')
  } catch {
    toast.show('匯出失敗', 'danger')
  }
}

function triggerImport() {
  importFileRef.value?.click()
}

async function handleImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  const text = await file.text()
  let payload: any
  try {
    payload = JSON.parse(text)
  } catch {
    toast.show('JSON 格式錯誤', 'danger')
    return
  }
  const catCount  = (payload.categories || []).length
  const prodCount = (payload.products   || []).length
  if (!confirm(`即將匯入：${catCount} 個分類、${prodCount} 個產品\n確定繼續？`)) return
  try {
    const { data } = await http.post('/product/import', payload)
    const res = data.result
    toast.show(
      `匯入完成：分類 +${res.created_categories}；產品 +${res.created_products} 更新${res.updated_products}`,
      res.errors?.length ? 'warning' : 'success'
    )
    await Promise.all([loadProducts(), loadCategories()])
  } catch (err: any) {
    toast.show(err?.response?.data?.message ?? '匯入失敗', 'danger')
  }
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadProducts()])
})
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-box-seam me-1"></i>產品資料</h6>
      <div class="toolbar">
        <!-- Category filter -->
        <select
          v-model="filterCatId"
          class="form-select form-select-sm"
          style="width: 140px"
        >
          <option value="">全部分類</option>
          <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
        </select>

        <!-- Keyword search -->
        <input
          v-model="keyword"
          type="text"
          class="form-control form-control-sm"
          style="width: 180px"
          placeholder="搜尋名稱/SKU"
          @keydown.enter="(e) => !e.isComposing && loadProducts()"
        />
        <button class="btn btn-sm btn-outline-secondary" @click="loadProducts" title="搜尋">
          <i class="bi bi-search"></i>
        </button>

        <!-- Export / Import -->
        <button class="btn btn-sm btn-outline-success" @click="exportProducts" title="匯出 JSON">
          <i class="bi bi-download"></i> 匯出
        </button>
        <button class="btn btn-sm btn-outline-warning" @click="triggerImport" title="匯入 JSON">
          <i class="bi bi-upload"></i> 匯入
        </button>
        <input
          ref="importFileRef"
          type="file"
          accept=".json"
          class="d-none"
          @change="handleImport"
        />

        <button class="btn btn-sm btn-primary" @click="openModal()">
          <i class="bi bi-plus-lg"></i> 新增產品
        </button>
      </div>
    </div>

    <!-- Batch action bar -->
    <Transition name="batch-bar">
      <div
        v-if="selectedIds.size > 0"
        class="batch-bar d-flex align-items-center gap-2 px-3 py-2"
      >
        <span class="text-white fw-semibold me-1">
          已選 {{ selectedIds.size }} 項
        </span>
        <div class="vr bg-white opacity-50 mx-1"></div>

        <!-- 批次分類 -->
        <select
          v-model="batchCatId"
          class="form-select form-select-sm"
          style="width: 140px"
        >
          <option value="">— 變更分類 —</option>
          <option value="__clear__">清除分類</option>
          <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
        </select>
        <button
          class="btn btn-sm btn-light"
          :disabled="!batchCatId || batchSaving"
          @click="batchApply({ category_id: batchCatId === '__clear__' ? null : batchCatId })"
        >
          套用
        </button>

        <div class="vr bg-white opacity-50 mx-1"></div>

        <!-- 狀態 -->
        <button
          class="btn btn-sm btn-success"
          :disabled="batchSaving"
          @click="batchApply({ status: 1 })"
          title="批次啟用"
        >
          <i class="bi bi-check-circle me-1"></i>啟用
        </button>
        <button
          class="btn btn-sm btn-secondary"
          :disabled="batchSaving"
          @click="batchApply({ status: 0 })"
          title="批次停用"
        >
          <i class="bi bi-slash-circle me-1"></i>停用
        </button>

        <div class="vr bg-white opacity-50 mx-1"></div>

        <!-- 刪除 -->
        <button
          class="btn btn-sm btn-danger"
          :disabled="batchSaving"
          @click="batchDelete"
        >
          <i class="bi bi-trash me-1"></i>刪除
        </button>

        <button class="btn btn-sm btn-outline-light ms-auto" @click="clearSelection">
          取消選取
        </button>
      </div>
    </Transition>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th style="width:36px">
              <input
                type="checkbox"
                class="form-check-input"
                :checked="allSelected"
                :indeterminate="someSelected"
                @change="toggleSelectAll"
              />
            </th>
            <th>名稱</th>
            <th>SKU</th>
            <th>分類</th>
            <th>單位</th>
            <th>售價</th>
            <th>成本</th>
            <th>最低庫存</th>
            <th>狀態</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!filteredProducts.length">
            <td colspan="10" class="text-center text-muted py-3">無產品資料</td>
          </tr>
          <tr
            v-for="p in filteredProducts"
            :key="p._id"
            :class="{ 'table-active': selectedIds.has(p._id) }"
            @click.exact="toggleSelect(p._id)"
            style="cursor:pointer"
          >
            <td @click.stop>
              <input
                type="checkbox"
                class="form-check-input"
                :checked="selectedIds.has(p._id)"
                @change="toggleSelect(p._id)"
              />
            </td>
            <td class="fw-semibold">{{ p.name }}</td>
            <td><code class="text-primary">{{ p.sku }}</code></td>
            <td>{{ catMap[p.category_id ?? ''] || '—' }}</td>
            <td>{{ p.unit }}</td>
            <td>${{ Number(p.sell_price ?? p.price ?? 0).toFixed(2) }}</td>
            <td>${{ Number(p.cost_price ?? p.cost  ?? 0).toFixed(2) }}</td>
            <td>{{ (p.min_stock ?? 0) > 0 ? p.min_stock : '—' }}</td>
            <td>
              <span
                class="badge"
                :class="(p.status ?? 1) === 1 ? 'bg-success' : 'bg-secondary'"
              >
                {{ (p.status ?? 1) === 1 ? '啟用' : '停用' }}
              </span>
            </td>
            <td @click.stop>
              <button
                class="btn btn-sm btn-outline-primary me-1"
                @click="openModal(p)"
                title="編輯"
              >
                <i class="bi bi-pencil"></i>
              </button>
              <button
                class="btn btn-sm btn-outline-danger"
                @click="del(p._id)"
                title="刪除"
              >
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Add / Edit Modal -->
  <Teleport to="body">
    <div
      v-if="showModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.5); z-index: 1055;"
      @click.self="showModal = false"
    >
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-box-seam me-1"></i>
              {{ form._id ? '編輯產品' : '新增產品' }}
            </h5>
            <button type="button" class="btn-close" @click="showModal = false"></button>
          </div>

          <div class="modal-body">
            <div class="row g-3">
              <!-- SKU -->
              <div class="col-md-6">
                <label class="form-label fw-semibold">
                  SKU <span class="text-danger">*</span>
                </label>
                <div class="input-group">
                  <input v-model="form.sku" type="text" class="form-control" />
                  <button
                    type="button"
                    class="btn btn-outline-secondary"
                    title="重新產生 SKU"
                    @click="form.sku = genSku()"
                  >
                    <i class="bi bi-arrow-clockwise"></i>
                  </button>
                </div>
              </div>

              <!-- Name -->
              <div class="col-md-6">
                <label class="form-label fw-semibold">
                  名稱 <span class="text-danger">*</span>
                </label>
                <input v-model="form.name" type="text" class="form-control" />
              </div>

              <!-- Barcode -->
              <div class="col-md-6">
                <label class="form-label fw-semibold">條碼</label>
                <input v-model="form.barcode" type="text" class="form-control" placeholder="EAN / UPC" />
              </div>

              <!-- Category -->
              <div class="col-md-6">
                <label class="form-label fw-semibold">分類</label>
                <select v-model="form.category_id" class="form-select">
                  <option value="">— 不指定 —</option>
                  <option
                    v-for="c in categories"
                    :key="c._id"
                    :value="c._id"
                  >{{ c.name }}</option>
                </select>
              </div>

              <!-- Unit -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">單位</label>
                <input v-model="form.unit" type="text" class="form-control" placeholder="個" />
              </div>

              <!-- Sell price -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">售價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input
                    v-model.number="form.sell_price"
                    type="number"
                    step="0.01"
                    min="0"
                    class="form-control"
                  />
                </div>
              </div>

              <!-- Cost price -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">成本價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input
                    v-model.number="form.cost_price"
                    type="number"
                    step="0.01"
                    min="0"
                    class="form-control"
                  />
                </div>
              </div>

              <!-- Min stock -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">最低庫存警示</label>
                <input
                  v-model.number="form.min_stock"
                  type="number"
                  min="0"
                  class="form-control"
                />
                <div class="form-text">0 = 不限制</div>
              </div>

              <!-- Status -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">狀態</label>
                <select v-model.number="form.status" class="form-select">
                  <option :value="1">啟用</option>
                  <option :value="0">停用</option>
                </select>
              </div>

              <!-- Description -->
              <div class="col-12">
                <label class="form-label fw-semibold">描述</label>
                <textarea v-model="form.description" class="form-control" rows="2"></textarea>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="save">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.batch-bar {
  background: #0d6efd;
  border-radius: 0;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.batch-bar-enter-active,
.batch-bar-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.batch-bar-enter-from,
.batch-bar-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.batch-bar-enter-to,
.batch-bar-leave-from {
  max-height: 60px;
  opacity: 1;
}
</style>
