<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore }    from '@/stores/auth'
import { useToastStore }   from '@/stores/toast'
import { warehouseApi }    from '@/api/warehouse'
import { productApi }      from '@/api/product'
import { settingsApi }     from '@/api/settings'
import { inventoryApi }    from '@/api/inventory'
import AppToast from '@/components/AppToast.vue'

const auth    = useAuthStore()
const toast   = useToastStore()

// ── 狀態 ───────────────────────────────────────────────────
const warehouses = ref([])
const products   = ref([])
const categories = ref([])
const items      = ref([])           // [{ product, qty }]
const type       = ref('inbound')    // inbound | outbound | consume
const warehouseId = ref('')
const remark     = ref('')
const catFilter  = ref('')
const search     = ref('')
const submitting = ref(false)

// 數量 overlay modal
const qtyModal   = ref(null)         // product being edited
const qtyInput   = ref(1)

// ── Computed ────────────────────────────────────────────────
const filteredProducts = computed(() => {
  let list = products.value
  if (catFilter.value) list = list.filter(p => p.category_id === catFilter.value)
  if (search.value) {
    const kw = search.value.toLowerCase()
    list = list.filter(p =>
      p.name?.toLowerCase().includes(kw) ||
      p.sku?.toLowerCase().includes(kw)
    )
  }
  return list
})

const totalQty = computed(() => items.value.reduce((s, i) => s + i.qty, 0))

const TYPE_LABELS = { inbound: '入庫', outbound: '出庫', consume: '消耗' }

// ── 方法 ────────────────────────────────────────────────────
function qtyOfProduct(product) {
  return items.value.find(i => i.product._id === product._id)?.qty ?? 0
}

function addProduct(product) {
  const existing = items.value.find(i => i.product._id === product._id)
  if (existing) { existing.qty++ }
  else { items.value.push({ product, qty: 1 }) }
}

function removeItem(idx) {
  items.value.splice(idx, 1)
}

function openQtyModal(product) {
  qtyModal.value = product
  qtyInput.value = qtyOfProduct(product) || 1
}

function confirmQty() {
  const qty = Math.max(1, parseInt(qtyInput.value) || 1)
  const existing = items.value.find(i => i.product._id === qtyModal.value._id)
  if (existing) { existing.qty = qty }
  else { items.value.push({ product: qtyModal.value, qty }) }
  qtyModal.value = null
}

async function submit() {
  if (!items.value.length) { toast.show('請至少選擇一項產品', 'danger'); return }
  if (!warehouseId.value)  { toast.show('請選擇倉庫', 'danger'); return }
  submitting.value = true
  try {
    await inventoryApi.batchIO({
      type:         type.value,
      warehouse_id: warehouseId.value,
      remark:       remark.value,
      items:        items.value.map(i => ({ product_id: i.product._id, qty: i.qty })),
    })
    toast.show(`${TYPE_LABELS[type.value]}成功！共 ${totalQty.value} 件`)
    items.value  = []
    remark.value = ''
  } catch (e) {
    toast.show(e?.response?.data?.message || '操作失敗', 'danger')
  } finally {
    submitting.value = false
  }
}

// ── 初始化 ──────────────────────────────────────────────────
async function init() {
  const [whRes, pdRes, catRes, setRes] = await Promise.allSettled([
    warehouseApi.getAll(),
    productApi.getProducts({ status: 1 }),
    productApi.getCategories(),
    settingsApi.get(),
  ])
  if (whRes.status === 'fulfilled') {
    warehouses.value = whRes.value.data?.data || whRes.value.data || []
  }
  if (pdRes.status === 'fulfilled') {
    products.value = pdRes.value.data?.data || pdRes.value.data || []
  }
  if (catRes.status === 'fulfilled') {
    categories.value = catRes.value.data?.data || catRes.value.data || []
  }
  if (setRes.status === 'fulfilled') {
    const s = setRes.value.data?.data || setRes.value.data || {}
    if (s.default_warehouse_id) warehouseId.value = s.default_warehouse_id
  }
  if (!warehouseId.value && warehouses.value.length) {
    warehouseId.value = warehouses.value[0]._id
  }
}

onMounted(init)
</script>

<template>
  <div class="qio-wrap d-flex flex-column" style="min-height:100vh;background:#f4f6fb">
    <!-- ── Topbar ─────────────────────────────────────────── -->
    <header class="qio-topbar d-flex align-items-center gap-3 px-3">
      <i class="bi bi-lightning-charge-fill text-warning fs-5"></i>
      <span class="fw-bold">快速出入庫</span>

      <!-- 操作類型 -->
      <div class="btn-group ms-2">
        <button v-for="t in ['inbound','outbound','consume']" :key="t"
                class="btn btn-sm"
                :class="type===t ? 'btn-primary' : 'btn-outline-secondary'"
                @click="type=t">
          {{ { inbound:'入庫', outbound:'出庫', consume:'消耗' }[t] }}
        </button>
      </div>

      <div class="ms-auto d-flex align-items-center gap-2">
        <span class="text-muted small">{{ auth.username }}</span>
        <a href="/admin/dashboard" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-grid-1x2"></i>
        </a>
      </div>
    </header>

    <!-- ── Main ──────────────────────────────────────────── -->
    <div class="d-flex flex-grow-1 overflow-hidden">
      <!-- Left: product grid -->
      <div class="qio-left d-flex flex-column">
        <div class="p-2 border-bottom bg-white d-flex gap-2">
          <input v-model="search" type="search" class="form-control form-control-sm"
                 placeholder="搜尋商品…" />
          <select v-model="catFilter" class="form-select form-select-sm" style="width:130px">
            <option value="">全部分類</option>
            <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
          </select>
        </div>
        <div class="product-grid flex-grow-1 overflow-auto p-2">
          <div v-for="p in filteredProducts" :key="p._id"
               class="product-card"
               :class="{ 'in-cart': qtyOfProduct(p) > 0 }"
               @click="addProduct(p)"
               @contextmenu.prevent="openQtyModal(p)">
            <div class="product-name">{{ p.name }}</div>
            <div class="product-sku text-muted">{{ p.sku }}</div>
            <div v-if="qtyOfProduct(p)" class="product-badge">{{ qtyOfProduct(p) }}</div>
          </div>
          <div v-if="!filteredProducts.length" class="text-center text-muted py-5 w-100">
            <i class="bi bi-inbox fs-2 d-block mb-2"></i>無商品
          </div>
        </div>
      </div>

      <!-- Right: item list + submit -->
      <div class="qio-right d-flex flex-column bg-white border-start">
        <div class="p-3 border-bottom">
          <div class="d-flex gap-2 align-items-center mb-2">
            <label class="fw-semibold small mb-0">倉庫</label>
            <select v-model="warehouseId" class="form-select form-select-sm flex-grow-1">
              <option value="">-- 選擇倉庫 --</option>
              <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
            </select>
          </div>
          <input v-model="remark" type="text" class="form-control form-control-sm"
                 placeholder="備註（可空白）" />
        </div>

        <div class="item-list flex-grow-1 overflow-auto p-2">
          <div v-if="!items.length" class="text-center text-muted py-4">
            <i class="bi bi-cart fs-2 d-block mb-2"></i>點擊商品加入
          </div>
          <div v-for="(it, idx) in items" :key="it.product._id" class="item-row">
            <div class="item-info">
              <div class="fw-semibold small">{{ it.product.name }}</div>
              <div class="text-muted" style="font-size:.75rem">{{ it.product.sku }}</div>
            </div>
            <div class="item-controls d-flex align-items-center gap-1">
              <button class="btn btn-sm btn-outline-secondary" @click="it.qty = Math.max(1, it.qty-1)">−</button>
              <input v-model.number="it.qty" type="number" min="1"
                     class="form-control form-control-sm text-center" style="width:56px" />
              <button class="btn btn-sm btn-outline-secondary" @click="it.qty++">+</button>
              <button class="btn btn-sm btn-outline-danger" @click="removeItem(idx)">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </div>

        <div class="p-3 border-top">
          <div class="text-muted small mb-2">共 {{ items.length }} 種 / {{ totalQty }} 件</div>
          <button class="btn btn-primary w-100 fw-semibold"
                  :disabled="submitting || !items.length"
                  @click="submit">
            <span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>
            確認{{ { inbound:'入庫', outbound:'出庫', consume:'消耗' }[type] }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 批量數量 Modal ─────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="qtyModal" class="modal-backdrop-custom" @click.self="qtyModal=null">
        <div class="qty-modal">
          <h6 class="fw-bold mb-3">{{ qtyModal.name }} — 輸入數量</h6>
          <input v-model.number="qtyInput" type="number" min="1"
                 class="form-control form-control-lg text-center mb-3"
                 @keydown.enter="confirmQty" ref="qtyInputEl" />
          <div class="d-flex gap-2">
            <button class="btn btn-secondary flex-grow-1" @click="qtyModal=null">取消</button>
            <button class="btn btn-primary flex-grow-1" @click="confirmQty">確認</button>
          </div>
        </div>
      </div>
    </Teleport>

    <AppToast />
  </div>
</template>

<style scoped>
.qio-topbar {
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e9ecef;
  flex-shrink: 0;
}
.qio-left  { flex: 1; min-width: 0; }
.qio-right { width: 320px; flex-shrink: 0; }

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
  align-content: start;
}
.product-card {
  background: #fff;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  position: relative;
  transition: border-color .15s, transform .1s;
  user-select: none;
}
.product-card:hover { border-color: #4da3ff; transform: translateY(-1px); }
.product-card.in-cart { border-color: #0d6efd; background: #f0f6ff; }
.product-name { font-weight: 600; font-size: .85rem; line-height: 1.3; }
.product-sku  { font-size: .72rem; margin-top: 2px; }
.product-badge {
  position: absolute; top: 5px; right: 5px;
  background: #0d6efd; color: #fff;
  border-radius: 50%; width: 20px; height: 20px;
  font-size: .7rem; display: flex; align-items: center; justify-content: center;
  font-weight: 700;
}

.item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 4px;
  border-bottom: 1px solid #f0f0f0;
  gap: 8px;
}
.item-info { min-width: 0; flex-shrink: 1; }

.modal-backdrop-custom {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 9000;
}
.qty-modal {
  background: #fff;
  border-radius: 14px;
  padding: 24px;
  width: 280px;
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}

@media (max-width: 767px) {
  .qio-left  { flex: none; height: 55vh; border-bottom: 1px solid #dee2e6; }
  .qio-right { width: 100%; height: calc(45vh - 52px); }
  .d-flex.flex-grow-1.overflow-hidden { flex-direction: column !important; }
}
</style>
