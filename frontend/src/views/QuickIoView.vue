<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore }    from '@/stores/auth'
import { useToastStore }   from '@/stores/toast'
import { warehouseApi }    from '@/api/warehouse'
import { productApi }      from '@/api/product'
import { settingsApi }     from '@/api/settings'
import { inventoryApi }    from '@/api/inventory'
import AppToast       from '@/components/AppToast.vue'
import BarcodeScanner from '@/components/BarcodeScanner.vue'

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

// 相機掃條碼
const scannerOpen = ref(false)

// [MOBILE] 手機版：上方「商品／清單」分頁＋底部固定操作列
const MOBILE_QUERY = '(max-width: 767.98px)'
const isMobile   = ref(false)
const mobileTab  = ref('products')   // products | cart
let mql = null
const onMql = (e) => { isMobile.value = e.matches }

// ── Computed ────────────────────────────────────────────────
const filteredProducts = computed(() => {
  let list = products.value
  if (catFilter.value) list = list.filter(p => p.category_id === catFilter.value)
  if (search.value) {
    const kw = search.value.toLowerCase()
    list = list.filter(p =>
      p.name?.toLowerCase().includes(kw) ||
      p.sku?.toLowerCase().includes(kw) ||
      p.barcode?.toLowerCase().includes(kw)
    )
  }
  return list
})

const totalQty = computed(() => items.value.reduce((s, i) => s + i.qty, 0))

const TYPE_LABELS = { inbound: '入庫', outbound: '出庫', consume: '消耗' }
const TYPE_ICONS  = { inbound: 'bi-box-arrow-in-down', outbound: 'bi-box-arrow-up', consume: 'bi-fire' }

// ── 方法 ────────────────────────────────────────────────────
function qtyOfProduct(product) {
  return items.value.find(i => i.product._id === product._id)?.qty ?? 0
}

function addProduct(product, qty = 1) {
  const existing = items.value.find(i => i.product._id === product._id)
  if (existing) { existing.qty += qty }
  else { items.value.push({ product, qty }) }
}

function removeItem(idx) {
  items.value.splice(idx, 1)
}

function clearItems() {
  if (items.value.length && confirm('確定要清空清單？')) items.value = []
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

// 長按商品卡開數量輸入（iOS Safari 長按不會觸發 contextmenu，需自行計時）
let pressTimer = null
let pressFired = false
function onPressStart(p) {
  pressFired = false
  pressTimer = setTimeout(() => { pressFired = true; openQtyModal(p) }, 500)
}
function onPressEnd() { clearTimeout(pressTimer); pressTimer = null }
function onCardClick(p) {
  if (pressFired) { pressFired = false; return }   // 長按已開視窗，不再額外 +1
  addProduct(p)
}

// ── 條碼：相機掃描、手持掃描槍（輸入後按 Enter）共用 ──────────
function findLocal(code) {
  const c = code.trim().toLowerCase()
  return products.value.find(p => p.barcode?.toLowerCase() === c)
      || products.value.find(p => p.sku?.toLowerCase() === c)
}

async function resolveCode(code) {
  const local = findLocal(code)
  if (local) return local
  try {
    const { data } = await productApi.getByBarcode(encodeURIComponent(code.trim()))
    const p = data?.data
    if (p && p.status !== 0) return p
    if (p) { toast.show(`「${p.name}」已停用，無法加入`, 'warning'); return null }
  } catch { /* 404：找不到 */ }
  toast.show(`找不到條碼 ${code}`, 'danger')
  return null
}

async function onScanned(code) {
  const p = await resolveCode(code)
  if (!p) return
  addProduct(p)
  toast.show(`已加入 ${p.name}（${qtyOfProduct(p)}）`, 'success', 1500)
}

async function onSearchEnter(e) {
  if (e.isComposing) return                 // 中文輸入法選字中的 Enter 不處理
  const code = search.value.trim()
  if (!code) return
  const exact = findLocal(code)
  if (exact) {
    addProduct(exact)
    toast.show(`已加入 ${exact.name}（${qtyOfProduct(exact)}）`, 'success', 1500)
    search.value = ''
    return
  }
  if (filteredProducts.value.length === 1) {   // 關鍵字只剩一項時直接加入
    addProduct(filteredProducts.value[0])
    search.value = ''
    return
  }
  if (/^[\w-]{6,}$/.test(code)) {             // 看起來像條碼才查後端
    const p = await resolveCode(code)
    if (p) { addProduct(p); search.value = '' }
  }
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
    mobileTab.value = 'products'
  } catch (e) {
    toast.show(e?.response?.data?.message || '操作失敗', 'danger')
  } finally {
    submitting.value = false
  }
}

// ── [PWA] 加入主畫面：只在本頁掛上 manifest 與 iOS meta，離開時移除 ──
const pwaTags = []
function addHeadTag(tag, attrs) {
  const el = document.createElement(tag)
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v))
  document.head.appendChild(el)
  pwaTags.push(el)
}
function mountPwa() {
  addHeadTag('link', { rel: 'manifest', href: '/quick-io.webmanifest' })
  addHeadTag('link', { rel: 'apple-touch-icon', href: '/icons/quick-io-180.png' })
  addHeadTag('meta', { name: 'apple-mobile-web-app-capable', content: 'yes' })
  addHeadTag('meta', { name: 'mobile-web-app-capable', content: 'yes' })
  addHeadTag('meta', { name: 'apple-mobile-web-app-title', content: '快速出入庫' })
  addHeadTag('meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'default' })
  addHeadTag('meta', { name: 'theme-color', content: '#ffffff' })
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

onMounted(() => {
  mql = window.matchMedia(MOBILE_QUERY)
  isMobile.value = mql.matches
  mql.addEventListener('change', onMql)
  mountPwa()
  init()
})
onBeforeUnmount(() => {
  mql?.removeEventListener('change', onMql)
  pwaTags.forEach(el => el.remove())
})
</script>

<template>
  <div class="qio-wrap" :class="{ 'is-mobile': isMobile }">
    <!-- ── Topbar ─────────────────────────────────────────── -->
    <header class="qio-topbar">
      <i class="bi bi-lightning-charge-fill text-warning fs-5"></i>
      <span class="fw-bold text-nowrap">快速出入庫</span>

      <!-- 操作類型（桌機在頂列；手機移到下方整列） -->
      <div v-if="!isMobile" class="btn-group ms-2">
        <button v-for="t in ['inbound','outbound','consume']" :key="t"
                class="btn btn-sm"
                :class="type===t ? 'btn-primary' : 'btn-outline-secondary'"
                @click="type=t">
          {{ TYPE_LABELS[t] }}
        </button>
      </div>

      <div class="ms-auto d-flex align-items-center gap-2">
        <span class="text-muted small text-truncate user-name">{{ auth.username }}</span>
        <a href="/admin/dashboard" class="btn btn-sm btn-outline-secondary btn-touch" title="回後台">
          <i class="bi bi-grid-1x2"></i>
        </a>
      </div>
    </header>

    <!-- 手機：操作類型 -->
    <div v-if="isMobile" class="type-switch">
      <button v-for="t in ['inbound','outbound','consume']" :key="t"
              class="btn"
              :class="type===t ? 'btn-primary' : 'btn-outline-secondary'"
              @click="type=t">
        <i class="bi me-1" :class="TYPE_ICONS[t]"></i>{{ TYPE_LABELS[t] }}
      </button>
    </div>

    <!-- ── Main ──────────────────────────────────────────── -->
    <div class="qio-main">
      <!-- 商品 -->
      <section v-show="!isMobile || mobileTab === 'products'" class="qio-left">
        <div class="search-bar">
          <div class="input-group">
            <input v-model="search" type="search" class="form-control"
                   placeholder="搜尋名稱／SKU，或用掃描槍輸入條碼"
                   enterkeyhint="search" autocomplete="off"
                   @keydown.enter.prevent="onSearchEnter" />
            <button v-if="search" class="btn btn-outline-secondary" @click="search=''" title="清除搜尋">
              <i class="bi bi-x-lg"></i>
            </button>
            <button class="btn btn-dark" @click="scannerOpen = true" title="相機掃條碼">
              <i class="bi bi-upc-scan"></i><span v-if="isMobile" class="ms-1">掃描</span>
            </button>
          </div>
          <select v-if="!isMobile" v-model="catFilter" class="form-select" style="width:140px">
            <option value="">全部分類</option>
            <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
          </select>
        </div>

        <!-- 手機：分類用可橫向滑動的按鈕 -->
        <div v-if="isMobile && categories.length" class="cat-chips">
          <button class="chip" :class="{ active: !catFilter }" @click="catFilter=''">全部</button>
          <button v-for="c in categories" :key="c._id" class="chip"
                  :class="{ active: catFilter === c._id }" @click="catFilter = c._id">
            {{ c.name }}
          </button>
        </div>

        <div class="product-grid">
          <div v-for="p in filteredProducts" :key="p._id"
               class="product-card"
               :class="{ 'in-cart': qtyOfProduct(p) > 0 }"
               @click="onCardClick(p)"
               @pointerdown="onPressStart(p)"
               @pointerup="onPressEnd" @pointerleave="onPressEnd" @pointercancel="onPressEnd"
               @contextmenu.prevent>
            <div class="product-name">{{ p.name }}</div>
            <div class="product-sku text-muted">{{ p.sku }}</div>
            <div v-if="qtyOfProduct(p)" class="product-badge">{{ qtyOfProduct(p) }}</div>
          </div>
          <div v-if="!filteredProducts.length" class="text-center text-muted py-5 empty">
            <i class="bi bi-inbox fs-2 d-block mb-2"></i>無商品
          </div>
        </div>
        <div class="hint text-muted">點一下 +1，長按輸入數量</div>
      </section>

      <!-- 清單 -->
      <section v-show="!isMobile || mobileTab === 'cart'" class="qio-right">
        <div class="p-3 border-bottom">
          <div class="d-flex gap-2 align-items-center mb-2">
            <label class="fw-semibold small mb-0 text-nowrap">倉庫</label>
            <select v-model="warehouseId" class="form-select flex-grow-1">
              <option value="">-- 選擇倉庫 --</option>
              <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
            </select>
          </div>
          <input v-model="remark" type="text" class="form-control" placeholder="備註（可空白）" />
        </div>

        <div class="item-list">
          <div v-if="!items.length" class="text-center text-muted py-4">
            <i class="bi bi-cart fs-2 d-block mb-2"></i>
            {{ isMobile ? '到「商品」點選或掃描條碼加入' : '點擊商品加入' }}
          </div>
          <div v-for="(it, idx) in items" :key="it.product._id" class="item-row">
            <div class="item-info">
              <div class="fw-semibold text-truncate">{{ it.product.name }}</div>
              <div class="text-muted small">{{ it.product.sku }}</div>
            </div>
            <div class="item-controls">
              <button class="btn btn-outline-secondary btn-touch" @click="it.qty = Math.max(1, it.qty-1)" aria-label="減少">−</button>
              <input v-model.number="it.qty" type="number" min="1" inputmode="numeric"
                     class="form-control text-center qty-input" />
              <button class="btn btn-outline-secondary btn-touch" @click="it.qty++" aria-label="增加">+</button>
              <button class="btn btn-outline-danger btn-touch" @click="removeItem(idx)" aria-label="移除">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </div>

        <div v-if="!isMobile" class="p-3 border-top">
          <div class="d-flex justify-content-between text-muted small mb-2">
            <span>共 {{ items.length }} 種 / {{ totalQty }} 件</span>
            <a v-if="items.length" href="#" class="text-danger" @click.prevent="clearItems">清空</a>
          </div>
          <button class="btn btn-primary w-100 fw-semibold"
                  :disabled="submitting || !items.length"
                  @click="submit">
            <span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>
            確認{{ TYPE_LABELS[type] }}
          </button>
        </div>
        <div v-else-if="items.length" class="px-3 pt-2 text-end">
          <a href="#" class="text-danger small" @click.prevent="clearItems">清空清單</a>
        </div>
      </section>
    </div>

    <!-- ── 手機：底部固定操作列 ───────────────────────────── -->
    <nav v-if="isMobile" class="bottom-bar">
      <button class="tab-btn" :class="{ active: mobileTab==='products' }" @click="mobileTab='products'">
        <i class="bi bi-grid-3x3-gap"></i><span>商品</span>
      </button>
      <button class="tab-btn" :class="{ active: mobileTab==='cart' }" @click="mobileTab='cart'">
        <i class="bi bi-list-check"></i><span>清單</span>
        <span v-if="items.length" class="tab-badge">{{ totalQty }}</span>
      </button>
      <button class="btn btn-primary submit-btn"
              :disabled="submitting || !items.length"
              @click="submit">
        <span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>
        確認{{ TYPE_LABELS[type] }}<span v-if="items.length">（{{ totalQty }}）</span>
      </button>
    </nav>

    <!-- ── 數量 Modal ─────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="qtyModal" class="modal-backdrop-custom" @click.self="qtyModal=null">
        <div class="qty-modal">
          <h6 class="fw-bold mb-3">{{ qtyModal.name }} — 輸入數量</h6>
          <div class="d-flex gap-2 mb-2">
            <button class="btn btn-outline-secondary btn-touch" @click="qtyInput = Math.max(1, (parseInt(qtyInput)||1) - 1)">−</button>
            <input v-model.number="qtyInput" type="number" min="1" inputmode="numeric"
                   class="form-control form-control-lg text-center"
                   @keydown.enter="confirmQty" />
            <button class="btn btn-outline-secondary btn-touch" @click="qtyInput = (parseInt(qtyInput)||0) + 1">+</button>
          </div>
          <div class="d-flex gap-2 mb-3">
            <button v-for="n in [5, 10, 20, 50]" :key="n" class="btn btn-light flex-grow-1"
                    @click="qtyInput = (parseInt(qtyInput)||0) + n">+{{ n }}</button>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-secondary flex-grow-1 btn-lg" @click="qtyModal=null">取消</button>
            <button class="btn btn-primary flex-grow-1 btn-lg" @click="confirmQty">確認</button>
          </div>
        </div>
      </div>
    </Teleport>

    <BarcodeScanner :open="scannerOpen" @detected="onScanned" @close="scannerOpen = false" />
    <AppToast />
  </div>
</template>

<style scoped>
.qio-wrap {
  display: flex; flex-direction: column;
  height: 100vh; height: 100dvh;
  background: #f4f6fb;
}
.qio-topbar {
  height: 52px; flex-shrink: 0;
  display: flex; align-items: center; gap: .75rem;
  padding: 0 1rem;
  padding-top: env(safe-area-inset-top);
  box-sizing: content-box;
  background: #fff; border-bottom: 1px solid #e9ecef;
}
.user-name { max-width: 120px; }

.qio-main { display: flex; flex: 1; min-height: 0; }
.qio-left  { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.qio-right { width: 320px; flex-shrink: 0; display: flex; flex-direction: column;
             background: #fff; border-left: 1px solid #dee2e6; }

.search-bar { display: flex; gap: .5rem; padding: .5rem; background: #fff; border-bottom: 1px solid #dee2e6; }
.search-bar .input-group { flex: 1; }

.product-grid {
  flex: 1; overflow: auto; padding: .5rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px; align-content: start;
}
.product-grid .empty { grid-column: 1 / -1; }
.product-card {
  background: #fff;
  border: 2px solid #e9ecef; border-radius: 10px;
  padding: 10px; position: relative;
  cursor: pointer; user-select: none; -webkit-user-select: none;
  -webkit-touch-callout: none; touch-action: manipulation;
  transition: border-color .15s, transform .1s;
}
.product-card:hover { border-color: #4da3ff; }
.product-card:active { transform: scale(.97); }
.product-card.in-cart { border-color: #0d6efd; background: #f0f6ff; }
.product-name { font-weight: 600; font-size: .85rem; line-height: 1.3; padding-right: 22px; }
.product-sku  { font-size: .72rem; margin-top: 2px; word-break: break-all; }
.product-badge {
  position: absolute; top: 6px; right: 6px;
  background: #0d6efd; color: #fff;
  border-radius: 999px; min-width: 22px; height: 22px; padding: 0 6px;
  font-size: .72rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.hint { font-size: .75rem; text-align: center; padding: 4px 0 6px; }

.item-list { flex: 1; overflow: auto; padding: .5rem; }
.item-row {
  display: flex; justify-content: space-between; align-items: center;
  gap: 8px; padding: 6px 4px; border-bottom: 1px solid #f0f0f0;
}
.item-info { min-width: 0; flex: 1; }
.item-controls { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.qty-input { width: 56px; padding-left: 2px; padding-right: 2px; }

.modal-backdrop-custom {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
}
.qty-modal {
  background: #fff; border-radius: 14px; padding: 20px;
  width: min(340px, 92vw);
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}

/* ══ [MOBILE] 手機版 ═══════════════════════════════════════ */
.type-switch { display: flex; gap: 6px; padding: 8px; background: #fff; border-bottom: 1px solid #e9ecef; }
.type-switch .btn { flex: 1; min-height: 44px; font-weight: 600; }

.cat-chips {
  display: flex; gap: 6px; overflow-x: auto; padding: 6px 8px;
  background: #fff; border-bottom: 1px solid #e9ecef;
  scrollbar-width: none; -webkit-overflow-scrolling: touch;
}
.cat-chips::-webkit-scrollbar { display: none; }
.chip {
  flex-shrink: 0; border: 1px solid #ced4da; background: #fff;
  border-radius: 999px; padding: 6px 14px; font-size: .9rem; min-height: 36px;
}
.chip.active { background: #0d6efd; border-color: #0d6efd; color: #fff; }

.bottom-bar {
  flex-shrink: 0; display: flex; align-items: stretch; gap: 6px;
  padding: 8px; padding-bottom: calc(8px + env(safe-area-inset-bottom));
  background: #fff; border-top: 1px solid #dee2e6;
  box-shadow: 0 -2px 10px rgba(0,0,0,.05);
}
.tab-btn {
  position: relative; width: 64px; flex-shrink: 0;
  border: 0; background: transparent; color: #6c757d; border-radius: 10px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  font-size: .75rem; gap: 2px;
}
.tab-btn i { font-size: 1.25rem; }
.tab-btn.active { color: #0d6efd; background: #eef4ff; }
.tab-badge {
  position: absolute; top: 2px; right: 8px;
  background: #dc3545; color: #fff; border-radius: 999px;
  min-width: 18px; height: 18px; padding: 0 5px; font-size: .68rem; line-height: 18px;
}
.submit-btn { flex: 1; min-height: 52px; font-size: 1.05rem; font-weight: 700; border-radius: 12px; }

.is-mobile .qio-main { flex-direction: column; }
.is-mobile .qio-right { width: 100%; border-left: 0; flex: 1; }
.is-mobile .product-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
.is-mobile .product-card { min-height: 76px; padding: 12px; }
.is-mobile .product-name { font-size: .95rem; }
.is-mobile .item-row { padding: 10px 4px; }
.is-mobile .qty-input { width: 64px; }
/* iOS：輸入框字級小於 16px 會在聚焦時自動放大畫面 */
.is-mobile input, .is-mobile select { font-size: 16px; }
.btn-touch { min-width: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; }
.qio-topbar .btn-touch { min-width: 36px; min-height: 36px; }
</style>
