<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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

// ── Form ───────────────────────────────────────────────────
interface ProductForm {
  _id:         string
  name:        string
  sku:         string
  category_id: string
  unit:        string
  price:       number
  cost:        number
  min_stock:   number
  description: string
  enabled:     boolean
}

const emptyForm = (): ProductForm => ({
  _id: '', name: '', sku: genSku(), category_id: '',
  unit: '個', price: 0, cost: 0, min_stock: 0,
  description: '', enabled: true,
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
      category_id: p.category_id ?? '',
      unit:        p.unit,
      price:       p.price ?? 0,
      cost:        p.cost ?? 0,
      min_stock:   p.min_stock ?? 0,
      description: p.description ?? '',
      enabled:     p.enabled ?? true,
    }
  } else if (form.value._id) {
    // 上次為編輯模式，切回新增時才清空
    form.value = emptyForm()
  }
  // 無 _id 且草稿存在 → 保留未儲存內容
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
      category_id: form.value.category_id || null,
      unit:        form.value.unit,
      price:       Number(form.value.price),
      cost:        Number(form.value.cost),
      min_stock:   Number(form.value.min_stock),
      description: form.value.description,
      enabled:     form.value.enabled,
    }
    if (form.value._id) {
      await http.put(`/api/product/${form.value._id}`, payload)
    } else {
      await http.post('/product/', payload)
    }
    toast.show('儲存成功', 'success')
    showModal.value = false
    if (isNew) form.value = emptyForm()  // 新增成功後清空草稿
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
    await http.delete(`/api/product/${id}`)
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
          @keydown.enter="loadProducts"
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

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
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
            <td colspan="9" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!filteredProducts.length">
            <td colspan="9" class="text-center text-muted py-3">無產品資料</td>
          </tr>
          <tr v-for="p in filteredProducts" :key="p._id">
            <td class="fw-semibold">{{ p.name }}</td>
            <td><code class="text-primary">{{ p.sku }}</code></td>
            <td>{{ catMap[p.category_id ?? ''] || '—' }}</td>
            <td>{{ p.unit }}</td>
            <td>${{ Number(p.price ?? 0).toFixed(2) }}</td>
            <td>${{ Number(p.cost  ?? 0).toFixed(2) }}</td>
            <td>{{ (p.min_stock ?? 0) > 0 ? p.min_stock : '—' }}</td>
            <td>
              <span
                class="badge"
                :class="p.enabled ? 'bg-success' : 'bg-secondary'"
              >
                {{ p.enabled ? '啟用' : '停用' }}
              </span>
            </td>
            <td>
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
              <div class="col-md-6">
                <label class="form-label fw-semibold">單位</label>
                <input v-model="form.unit" type="text" class="form-control" placeholder="個" />
              </div>

              <!-- Price -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">售價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input
                    v-model.number="form.price"
                    type="number"
                    step="0.01"
                    min="0"
                    class="form-control"
                  />
                </div>
              </div>

              <!-- Cost -->
              <div class="col-md-4">
                <label class="form-label fw-semibold">成本價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input
                    v-model.number="form.cost"
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

              <!-- Description -->
              <div class="col-12">
                <label class="form-label fw-semibold">描述</label>
                <textarea v-model="form.description" class="form-control" rows="2"></textarea>
              </div>

              <!-- Enabled toggle (edit mode) -->
              <div class="col-12">
                <div class="form-check form-switch">
                  <input
                    v-model="form.enabled"
                    class="form-check-input"
                    type="checkbox"
                    id="prod-enabled"
                  />
                  <label class="form-check-label fw-semibold" for="prod-enabled">
                    {{ form.enabled ? '啟用' : '停用' }}
                  </label>
                </div>
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
