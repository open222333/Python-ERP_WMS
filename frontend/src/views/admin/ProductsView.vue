<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import { fetchAllPages } from '@/api/paging'
import type { Category, Product } from '@/types'
import { appConfirm } from '@/composables/useConfirm'
// [U10] 2026-11 拆分：分類分頁與產品表單彈窗移至 components/products/
import ProductCategoriesTab from '@/components/products/ProductCategoriesTab.vue'
import ProductFormModal from '@/components/products/ProductFormModal.vue'

const toast = useToastStore()

// ── Tab ────────────────────────────────────────────────────
const activeTab = ref<'products' | 'categories'>('products')

// ── State ──────────────────────────────────────────────────
const products   = ref<Product[]>([])
const categories = ref<Category[]>([])
const loading    = ref(false)

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
  if (!(await appConfirm(`確定刪除選取的 ${ids.length} 個產品？此操作無法復原。`, { danger: true }))) return
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
    products.value = await fetchAllPages('/product/')   // [U3] 原本只顯示前 200 筆
  } catch {
    toast.show('載入產品失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Modal ──────────────────────────────────────────────────
const productModal = ref<InstanceType<typeof ProductFormModal> | null>(null)
function openModal(p?: Product) { productModal.value?.open(p) }

// ── Delete ─────────────────────────────────────────────────
async function del(id: string) {
  if (!(await appConfirm('確定要刪除此產品？', { danger: true }))) return
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
  if (!(await appConfirm(`即將匯入：${catCount} 個分類、${prodCount} 個產品\n確定繼續？`))) return
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
  <!-- Tab 切換 -->
  <ul class="nav nav-tabs mb-3" style="border-bottom:none">
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'products' }"
         href="#" @click.prevent="activeTab = 'products'">
        <i class="bi bi-box-seam me-1"></i>產品資料
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'categories' }"
         href="#" @click.prevent="activeTab = 'categories'">
        <i class="bi bi-tags me-1"></i>產品分類
      </a>
    </li>
  </ul>

  <!-- ── 產品資料 Tab ─────────────────────────────────── -->
  <div v-if="activeTab === 'products'" class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-box-seam me-1"></i>產品資料</h6>
      <div class="toolbar">
        <!-- Category filter -->
        <select
          v-model="filterCatId"
          class="form-select form-select-sm wpx-140"
        >
          <option value="">全部分類</option>
          <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
        </select>

        <!-- Keyword search -->
        <input
          v-model="keyword"
          type="search"
          @search="loadProducts()"
          class="form-control form-control-sm wpx-180"
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
          class="form-select form-select-sm wpx-140"
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
      <table v-stack-table class="table mb-0">
        <thead>
          <tr>
            <th class="wpx-36">
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
          <tr class="cursor-pointer"
            v-for="p in filteredProducts"
            :key="p._id"
            :class="{ 'table-active': selectedIds.has(p._id) }"
            @click.exact="toggleSelect(p._id)">
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
  </div><!-- end 產品資料 tab -->

  <!-- ── 產品分類 Tab ─────────────────────────────────── -->
  <ProductCategoriesTab v-if="activeTab === 'categories'" :categories="categories" @reload="loadCategories" />

  <!-- Add / Edit Modal -->
  <ProductFormModal ref="productModal" :categories="categories" @saved="loadProducts" />
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
