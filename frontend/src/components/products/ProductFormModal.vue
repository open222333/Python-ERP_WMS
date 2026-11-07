<!-- [U10] 自 views/admin/ProductsView.vue 拆出 -->
<script setup lang="ts">
// 產品新增／編輯彈窗。元件常駐（只切換 showModal），關閉不儲存時新增表單保留為草稿，儲存成功才清空
import { ref } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import type { Category, Product } from '@/types'
import { useFieldErrors } from '@/composables/useFieldErrors'

defineProps<{ categories: Category[] }>()
const emit = defineEmits<{ (e: 'saved'): void }>()

const toast     = useToastStore()
const fe        = useFieldErrors()   // [U9]
const saving    = ref(false)
const showModal = ref(false)

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

// ── Modal ──────────────────────────────────────────────────
function open(p?: Product) {
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
  fe.clear()
  showModal.value = true
}

// ── Save ───────────────────────────────────────────────────
async function save() {
  // [U9] 錯誤標在欄位旁，不再只靠 toast
  if (!fe.check({
    sku:        [!form.value.sku.trim(),  '請填寫 SKU'],
    name:       [!form.value.name.trim(), '請填寫名稱'],
    sell_price: [Number(form.value.sell_price) < 0, '售價不可為負數'],
    cost_price: [Number(form.value.cost_price) < 0, '成本不可為負數'],
  })) return
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
    emit('saved')
  } catch (e: any) {
    const msg = e?.response?.data?.message ?? '儲存失敗'
    if (e?.response?.status === 409 && msg.includes('SKU')) fe.set('sku', msg)   // SKU 已存在
    toast.show(msg, 'danger')
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<template>
<!-- Add / Edit Modal -->
<Teleport to="body">
  <div
    v-if="showModal"
    class="modal d-block bg-dim-50 z-1055"
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
                <input v-model="form.sku" type="text" class="form-control" data-field="sku"
                       :class="{ 'is-invalid': fe.errors.sku }" @input="fe.clear('sku')" />
                <button
                  type="button"
                  class="btn btn-outline-secondary"
                  title="重新產生 SKU"
                  @click="form.sku = genSku()"
                >
                  <i class="bi bi-arrow-clockwise"></i>
                </button>
                <div class="invalid-feedback">{{ fe.errors.sku }}</div>
              </div>
            </div>

            <!-- Name -->
            <div class="col-md-6">
              <label class="form-label fw-semibold">
                名稱 <span class="text-danger">*</span>
              </label>
              <input v-model="form.name" type="text" class="form-control" data-field="name"
                     :class="{ 'is-invalid': fe.errors.name }" @input="fe.clear('name')" />
              <div class="invalid-feedback">{{ fe.errors.name }}</div>
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
                  data-field="sell_price"
                  :class="{ 'is-invalid': fe.errors.sell_price }"
                  @input="fe.clear('sell_price')"
                />
                <div class="invalid-feedback">{{ fe.errors.sell_price }}</div>
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
                  data-field="cost_price"
                  :class="{ 'is-invalid': fe.errors.cost_price }"
                  @input="fe.clear('cost_price')"
                />
                <div class="invalid-feedback">{{ fe.errors.cost_price }}</div>
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
