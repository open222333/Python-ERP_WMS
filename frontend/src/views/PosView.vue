<template>
  <!-- 直向提示 -->
  <div id="rotate-hint">
    <i class="bi bi-phone-landscape"></i>
    <div style="font-size:1.1rem;font-weight:600">請旋轉裝置為橫向使用</div>
    <div style="font-size:.85rem;color:#94a3b8">POS 收銀系統需要橫向模式</div>
  </div>

  <div id="pos-root">
    <!-- ── Topbar ─────────────────────────────────────── -->
    <div id="topbar">
      <div class="tb-logo"><i class="bi bi-cash-register"></i>POS 收銀</div>
      <div class="tb-sep"></div>
      <select v-model="selectedWarehouse" class="form-select" style="width:150px">
        <option value="">全部倉庫</option>
        <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
      </select>
      <select v-model="selectedMenu" class="form-select" style="width:160px" @change="onMenuChange">
        <option value="">全部商品</option>
        <option v-for="m in menus" :key="m._id" :value="m._id">{{ m.name }}</option>
      </select>
      <div id="scan-bar">
        <i class="bi bi-upc-scan scan-icon"></i>
        <input v-model="scanInput" type="text" placeholder="掃描條碼…"
               autocomplete="off" @keydown.enter="onScan" ref="scanRef" />
      </div>
      <div style="flex:1"></div>
      <span id="topbar-clock">{{ clock }}</span>
      <div class="tb-sep"></div>
      <span id="topbar-user">👤 {{ auth.username }}</span>
      <button class="tb-btn" @click="showHistory = true">
        <i class="bi bi-clock-history"></i>銷售記錄
      </button>
      <button class="tb-btn danger" @click="handleLogout">
        <i class="bi bi-box-arrow-right"></i>登出
      </button>
    </div>

    <!-- ── Main ──────────────────────────────────────── -->
    <div id="main">
      <!-- Left: Items -->
      <div id="panel-products">
        <div id="product-toolbar">
          <div id="prod-search-wrap">
            <i class="bi bi-search"></i>
            <input v-model="prodSearch" type="text" id="prod-search" placeholder="搜尋名稱…" />
          </div>
          <!-- 分類下拉只在商品模式顯示 -->
          <select v-if="!isMenuMode" v-model="prodCat" id="prod-cat">
            <option value="">全部分類</option>
            <option v-for="c in categories" :key="c._id" :value="c._id">{{ c.name }}</option>
          </select>
        </div>

        <!-- Category tabs -->
        <div id="cat-tabs">
          <button v-for="tab in catTabs" :key="tab"
                  class="cat-tab" :class="{ active: activeCat === tab }"
                  @click="activeCat = tab">{{ tab }}</button>
        </div>

        <!-- Item grid -->
        <div id="product-grid">
          <div v-if="filteredItems.length === 0" class="text-center text-muted py-4" style="grid-column:1/-1">
            <i class="bi bi-inbox fs-2"></i><p class="mt-2">無符合商品</p>
          </div>
          <div v-for="item in filteredItems" :key="item._id"
               class="prod-card" @click="handleItemClick(item)">
            <div class="pc-name">{{ item.name }}</div>
            <div class="pc-sub">{{ isMenuMode ? (item.category || '') : (item.sku || '') }}</div>
            <div class="pc-price">NT$ {{ item.price }}</div>
            <div v-if="isMenuMode && item.applied_groups?.length" class="pc-custom-badge">
              <i class="bi bi-sliders2"></i>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Cart -->
      <div id="panel-cart">
        <div id="cart-header">
          <div>
            <h6 style="display:inline"><i class="bi bi-cart3 me-1"></i>購物車</h6>
            <span v-if="cart.length" id="cart-count">{{ cartTotal.count }}</span>
          </div>
          <button class="tb-btn danger" style="padding:4px 10px;font-size:.75rem" @click="clearCart">
            <i class="bi bi-trash"></i>清空
          </button>
        </div>

        <div id="cart-empty" :class="{ hidden: cart.length > 0 }">
          <i class="bi bi-cart-x"></i>
          <span>購物車空空如也</span>
        </div>

        <div id="cart-items">
          <div v-for="(row, idx) in cart" :key="idx" class="cart-row">
            <div class="cart-info">
              <div class="cart-name">{{ row.item.name }}</div>
              <div v-if="row.selections?.length" class="cart-options">
                {{ row.selections.map(s => s.choice_name).join(' · ') }}
              </div>
              <div v-else class="cart-sku">{{ row.item.sku || '' }}</div>
            </div>
            <div class="cart-qty-ctrl">
              <button class="qty-btn" @click="changeQty(idx, -1)">－</button>
              <span class="qty-val">{{ row.quantity }}</span>
              <button class="qty-btn" @click="changeQty(idx, 1)">＋</button>
            </div>
            <div class="cart-price">NT$ {{ rowPrice(row) * row.quantity }}</div>
            <i class="bi bi-x-circle cart-del" @click="removeCart(idx)"></i>
          </div>
        </div>

        <div id="cart-footer">
          <div class="cf-row">
            <span class="cf-label">小計</span>
            <span class="cf-val">NT$ {{ cartTotal.subtotal }}</span>
          </div>
          <div class="cf-row">
            <span class="cf-label">折扣</span>
            <div style="display:flex;align-items:center;gap:4px">
              <span style="color:#9ca3af;font-size:.82rem">$</span>
              <input v-model.number="discount" type="number" min="0" step="1"
                     style="width:80px;border:1.5px solid #e2e8f0;border-radius:7px;padding:4px 8px;text-align:right;font-size:.85rem;font-weight:600" />
            </div>
          </div>
          <div class="cf-row" id="cf-total-row">
            <span id="cf-total-lbl">合計</span>
            <span id="cf-total">NT$ {{ cartTotal.total }}</span>
          </div>
          <button id="btn-checkout" :disabled="cart.length === 0" @click="showPayment = true">
            <i class="bi bi-credit-card-2-front-fill" style="font-size:1.1rem"></i>結帳
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Toast area -->
  <AppToast />

  <!-- ── 客製化選項 Modal ─────────────────────────── -->
  <Teleport to="body">
    <div v-if="showCustomModal" class="modal-backdrop-custom" @click.self="showCustomModal = false">
      <div class="modal-box-custom">
        <div class="modal-header">
          <div>
            <h5 class="modal-title"><i class="bi bi-sliders2 me-1"></i>{{ customTarget?.name }}</h5>
            <div class="text-muted small mt-1">NT$ {{ customTarget?.price }}</div>
          </div>
          <button class="btn-close" @click="showCustomModal = false"></button>
        </div>
        <div class="modal-body" style="max-height:60vh;overflow-y:auto">
          <div v-for="grp in customTarget?.applied_groups" :key="grp._id" class="og-section">
            <div class="og-title">
              {{ grp.name }}
              <span v-if="grp.required" class="og-badge required">必選</span>
              <span v-if="grp.type === 'multiple'" class="og-badge multi">可複選</span>
            </div>
            <!-- Single: radio pill -->
            <div class="og-choices">
              <label v-for="ch in grp.choices" :key="ch._id"
                     class="choice-pill"
                     :class="{ active: customSelections[grp._id]?.includes(ch._id) }">
                <input v-if="grp.type === 'single'" type="radio"
                       :name="`grp-${grp._id}`"
                       :checked="customSelections[grp._id]?.[0] === ch._id"
                       @change="customSelections[grp._id] = [ch._id]"
                       style="display:none" />
                <input v-else type="checkbox"
                       :checked="customSelections[grp._id]?.includes(ch._id)"
                       @change="toggleMultiChoice(grp._id, ch._id)"
                       style="display:none" />
                {{ ch.name }}
                <span v-if="ch.extra_price > 0" class="choice-extra">+{{ ch.extra_price }}</span>
              </label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCustomModal = false">取消</button>
          <button class="btn btn-primary fw-bold px-4" @click="confirmCustom">
            <i class="bi bi-cart-plus me-1"></i>加入購物車
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── Payment Modal ─────────────────────────────── -->
  <Teleport to="body">
    <div v-if="showPayment" class="modal-backdrop-custom" @click.self="showPayment = false">
      <div class="modal-box-sm">
        <div class="modal-header">
          <h5 class="modal-title"><i class="bi bi-credit-card me-1"></i>付款</h5>
          <button class="btn-close" @click="showPayment = false"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3 text-center">
            <div class="text-muted small">應付金額</div>
            <div class="fs-2 fw-bold text-primary">NT$ {{ cartTotal.total }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">付款方式</label>
            <div class="d-flex flex-wrap gap-1">
              <button v-for="pm in enabledPayMethods" :key="pm.id"
                      class="btn btn-sm" :class="selectedPayMethod === pm.id ? 'btn-primary' : 'btn-outline-secondary'"
                      @click="selectedPayMethod = pm.id; calcChange()">{{ pm.label }}</button>
            </div>
          </div>
          <div v-if="currentPayHasCash" class="mb-2">
            <label class="form-label small fw-semibold">收現</label>
            <div class="input-group">
              <span class="input-group-text">$</span>
              <input v-model.number="cashReceived" type="number" class="form-control" min="0" step="1" @input="calcChange" />
            </div>
            <div class="mt-1 small text-muted" v-if="changeAmt >= 0">找零：NT$ {{ changeAmt }}</div>
          </div>
          <div class="mb-2">
            <label class="form-label small fw-semibold">備註</label>
            <input v-model="payRemark" type="text" class="form-control form-control-sm" placeholder="選填" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showPayment = false">取消</button>
          <button class="btn btn-success fw-bold" :disabled="checkoutLoading" @click="confirmCheckout">
            <span v-if="checkoutLoading" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-check-lg me-1"></i>確認結帳
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import AppToast from '@/components/AppToast.vue'

const auth   = useAuthStore()
const toast  = useToastStore()
const router = useRouter()

// ── Types ─────────────────────────────────────────
interface SelectionItem {
  group_id:    string
  group_name:  string
  choice_id:   string
  choice_name: string
  extra_price: number
}

interface CartRow {
  item:       any
  quantity:   number
  selections: SelectionItem[]
}

// ── State ─────────────────────────────────────────
const products   = ref<any[]>([])
const categories = ref<any[]>([])
const warehouses = ref<any[]>([])
const menus      = ref<any[]>([])
const payMethods = ref<any[]>([{ id: 'cash', label: '現金', enabled: true, has_cash: true }])

const selectedWarehouse = ref('')
const selectedMenu      = ref('')
const prodSearch        = ref('')
const prodCat           = ref('')
const activeCat         = ref('全部')
const scanInput         = ref('')
const scanRef           = ref<HTMLInputElement>()

const cart     = ref<CartRow[]>([])
const discount = ref(0)

const showPayment       = ref(false)
const showHistory       = ref(false)
const selectedPayMethod = ref('cash')
const cashReceived      = ref(0)
const changeAmt         = ref(0)
const payRemark         = ref('')
const checkoutLoading   = ref(false)

// ── 客製化 Modal ──────────────────────────────────
const showCustomModal  = ref(false)
const customTarget     = ref<any>(null)
const customSelections = ref<Record<string, string[]>>({})

const clock = ref('')
let clockTimer: ReturnType<typeof setInterval>

// ── Computed ──────────────────────────────────────
const isMenuMode = computed(() => !!selectedMenu.value)

const activeMenuItems = computed(() => {
  if (!selectedMenu.value) return []
  const menu = menus.value.find((m: any) => m._id === selectedMenu.value)
  return ((menu?.items || []) as any[]).filter((i: any) => i.status === 1)
})

const displayedItems = computed<any[]>(() => {
  if (isMenuMode.value) return activeMenuItems.value
  return products.value
})

const catTabs = computed(() => {
  if (isMenuMode.value) {
    const cats = [...new Set(activeMenuItems.value.map((i: any) => (i.category || '其他') as string))]
    return ['全部', ...cats]
  }
  const cats = [...new Set(displayedItems.value.map((p: any) => (p._category_name || '其他') as string))]
  return ['全部', ...cats]
})

const filteredItems = computed(() => {
  let list = displayedItems.value
  if (activeCat.value && activeCat.value !== '全部') {
    if (isMenuMode.value) {
      list = list.filter((i: any) => (i.category || '其他') === activeCat.value)
    } else {
      list = list.filter((p: any) => (p._category_name || '其他') === activeCat.value)
    }
  }
  if (!isMenuMode.value && prodCat.value) {
    list = list.filter((p: any) => p.category_id === prodCat.value)
  }
  if (prodSearch.value) {
    const q = prodSearch.value.toLowerCase()
    list = list.filter((p: any) =>
      p.name.toLowerCase().includes(q) || (p.sku || '').toLowerCase().includes(q)
    )
  }
  return list
})

function rowPrice(row: CartRow): number {
  const extra = (row.selections || []).reduce((s: number, sel: SelectionItem) => s + (sel.extra_price || 0), 0)
  return (row.item.price || 0) + extra
}

const cartTotal = computed(() => {
  const subtotal = cart.value.reduce((s, r) => s + rowPrice(r) * r.quantity, 0)
  const total    = Math.max(0, subtotal - discount.value)
  const count    = cart.value.reduce((s, r) => s + r.quantity, 0)
  return { subtotal, total, count }
})

const enabledPayMethods = computed(() => payMethods.value.filter((m: any) => m.enabled !== false))
const currentPayHasCash = computed(() => {
  const m = payMethods.value.find((m: any) => m.id === selectedPayMethod.value)
  return m?.has_cash ?? false
})

// ── Methods ───────────────────────────────────────
function tickClock() {
  clock.value = new Date().toLocaleTimeString('zh-TW', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function selKey(selections: SelectionItem[]): string {
  return selections.map(s => `${s.group_id}:${s.choice_id}`).sort().join('|')
}

function commitToCart(item: any, selections: SelectionItem[]) {
  const key = selKey(selections)
  const idx = cart.value.findIndex(
    r => r.item._id === item._id && selKey(r.selections) === key
  )
  if (idx >= 0) {
    cart.value[idx].quantity++
  } else {
    cart.value.push({ item, quantity: 1, selections })
  }
}

function handleItemClick(item: any) {
  const groups: any[] = item.applied_groups || []
  if (isMenuMode.value && groups.length > 0) {
    customTarget.value = item
    // 預設選取每組的 is_default 選項
    const sel: Record<string, string[]> = {}
    for (const grp of groups) {
      if (grp.type === 'single') {
        const def = (grp.choices || []).find((c: any) => c.is_default)
        sel[grp._id] = def ? [def._id] : []
      } else {
        sel[grp._id] = (grp.choices || [])
          .filter((c: any) => c.is_default)
          .map((c: any) => c._id)
      }
    }
    customSelections.value = sel
    showCustomModal.value = true
  } else {
    commitToCart(item, [])
  }
}

function toggleMultiChoice(groupId: string, choiceId: string) {
  const arr = customSelections.value[groupId] || []
  const i = arr.indexOf(choiceId)
  customSelections.value[groupId] = i >= 0
    ? arr.filter(id => id !== choiceId)
    : [...arr, choiceId]
}

function confirmCustom() {
  const groups: any[] = customTarget.value?.applied_groups || []
  // 驗證必選
  for (const grp of groups) {
    if (grp.required && !(customSelections.value[grp._id]?.length)) {
      toast.show(`請選擇「${grp.name}」`, 'danger')
      return
    }
  }
  // 建立選擇陣列
  const selections: SelectionItem[] = []
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const choice = (grp.choices || []).find((c: any) => c._id === cid)
      if (choice) {
        selections.push({
          group_id:    grp._id,
          group_name:  grp.name,
          choice_id:   cid,
          choice_name: choice.name,
          extra_price: choice.extra_price || 0,
        })
      }
    }
  }
  commitToCart(customTarget.value, selections)
  showCustomModal.value = false
}

function changeQty(idx: number, delta: number) {
  cart.value[idx].quantity += delta
  if (cart.value[idx].quantity <= 0) cart.value.splice(idx, 1)
}

function removeCart(idx: number) { cart.value.splice(idx, 1) }
function clearCart() { cart.value = []; discount.value = 0 }

function onScan() {
  const sku = scanInput.value.trim()
  if (!sku) return
  const p = products.value.find((p: any) => p.sku === sku)
  if (p) { commitToCart(p, []); scanInput.value = '' }
  else toast.show(`找不到條碼：${sku}`, 'danger')
}

function onMenuChange() {
  activeCat.value  = '全部'
  prodSearch.value = ''
}

function calcChange() {
  changeAmt.value = cashReceived.value - cartTotal.value.total
}

async function confirmCheckout() {
  if (!selectedWarehouse.value) return toast.show('請先選擇倉庫', 'danger')
  if (!selectedPayMethod.value) return toast.show('請選擇付款方式', 'danger')
  if (currentPayHasCash.value && cashReceived.value < cartTotal.value.total)
    return toast.show('收現金額不足', 'danger')

  checkoutLoading.value = true
  try {
    const items = cart.value.map(r => ({
      product_name:    r.item.name,
      product_sku:     r.item.sku || '',
      unit:            '份',
      quantity:        r.quantity,
      unit_price:      rowPrice(r),
      // 庫存扣減用
      consume_inventory: r.item.consume_inventory ?? true,
      linked_products:   r.item.linked_products  || [],
      product_id:        r.item.product_id       || null,
      // 客製化記錄（存入訂單）
      customizations_selected: (r.selections || []).map(s => ({
        group_name:  s.group_name,
        choice_name: s.choice_name,
        extra_price: s.extra_price,
      })),
    }))

    const payment = {
      type:        selectedPayMethod.value,
      cash_amount: currentPayHasCash.value ? cashReceived.value : 0,
      card_amount: currentPayHasCash.value ? 0 : cartTotal.value.total,
    }

    await http.post('/pos/sale', {
      warehouse_id: selectedWarehouse.value,
      items,
      payment,
      discount: discount.value,
      remark:   payRemark.value,
    })
    toast.show('結帳成功！', 'success')
    clearCart()
    showPayment.value       = false
    payRemark.value         = ''
    cashReceived.value      = 0
    selectedPayMethod.value = enabledPayMethods.value[0]?.id ?? 'cash'
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '結帳失敗', 'danger')
  } finally {
    checkoutLoading.value = false
  }
}

async function handleLogout() {
  auth.logout()
  await router.push('/login')
}

async function boot() {
  try {
    const [pr, cr, wr, mr, pmr, sr] = await Promise.all([
      http.get('/product/?status=1'),
      http.get('/product/category/'),
      http.get('/warehouse/'),
      http.get('/menu/?status=1'),
      http.get('/pos/payment-methods'),
      http.get('/settings/'),
    ])
    const catMap: Record<string, string> = {}
    ;(cr.data.data || []).forEach((c: any) => { catMap[c._id] = c.name })
    categories.value = cr.data.data || []
    products.value   = (pr.data.data || []).map((p: any) => ({
      ...p,
      _category_name: catMap[p.category_id] || '其他',
    }))
    warehouses.value = wr.data.data || []
    menus.value      = mr.data.data || []
    const enabled = (pmr.data.data || []).filter((m: any) => m.enabled !== false)
    if (enabled.length) payMethods.value = enabled
    selectedPayMethod.value = payMethods.value[0]?.id ?? 'cash'

    // ── 套用系統設定預設值 ──────────────────────
    const s = sr.data?.data || {}
    if (s.default_warehouse_id) {
      const wh = (warehouses.value as any[]).find((w: any) => w._id === s.default_warehouse_id)
      if (wh) selectedWarehouse.value = s.default_warehouse_id
    }
    if (s.pos_default_menu_id) {
      const m = (menus.value as any[]).find((m: any) => m._id === s.pos_default_menu_id)
      if (m) {
        selectedMenu.value = s.pos_default_menu_id
        onMenuChange()
      }
    }
  } catch {
    toast.show('載入商品失敗', 'danger')
  }
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  boot()
  setTimeout(() => scanRef.value?.focus(), 300)
})
onUnmounted(() => clearInterval(clockTimer))
</script>

<style scoped>
:root {
  --accent:      #4f6ef7;
  --accent-dark: #3a56d4;
  --topbar-h:    56px;
  --cart-w:      360px;
}
@media (min-width: 1100px) { :root { --cart-w: 400px; } }
@media (max-width:  820px) { :root { --cart-w: 300px; } }

#rotate-hint {
  display: none;
  position: fixed; inset: 0; z-index: 99999;
  background: #1e2235; color: #fff;
  flex-direction: column; align-items: center; justify-content: center; gap: 16px;
}
@media (orientation: portrait) { #rotate-hint { display: flex; } }

#pos-root {
  position: fixed; inset: 0;
  display: flex; flex-direction: column;
  overflow: hidden; background: #eef0f5;
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 14px;
}

/* Topbar */
#topbar {
  height: var(--topbar-h);
  background: #1e2235;
  display: flex; align-items: center; gap: 12px;
  padding: 0 16px; flex-shrink: 0; color: #fff;
}
.tb-logo { font-weight: 700; font-size: 1rem; letter-spacing: .5px;
           white-space: nowrap; display: flex; align-items: center; gap: 6px; }
.tb-logo i { color: #7c9cff; font-size: 1.2rem; }
#topbar .form-select { background: #2c3148; border-color: #3d4566; color: #e2e8f0; font-size: .82rem; }
#scan-bar { flex: 0 0 220px; position: relative; }
#scan-bar input { background: #2c3148; border: 1px solid #3d4566; color: #e2e8f0;
                  border-radius: 8px; padding: 5px 10px 5px 32px; width: 100%; font-size: .82rem; }
#scan-bar input:focus { outline: none; border-color: var(--accent); }
.scan-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #6b7280; pointer-events: none; }
#topbar-clock, #topbar-user { font-size: .82rem; color: #94a3b8; white-space: nowrap; }
.tb-btn { background: #2c3148; border: 1px solid #3d4566; color: #cbd5e1;
          border-radius: 7px; padding: 5px 10px; font-size: .78rem; cursor: pointer;
          display: flex; align-items: center; gap: 5px; white-space: nowrap; transition: background .15s; }
.tb-btn:hover { background: #3a4060; }
.tb-btn.danger { border-color: #7f1d1d; color: #fca5a5; }
.tb-btn.danger:hover { background: #7f1d1d; }
.tb-sep { width: 1px; height: 24px; background: #3d4566; flex-shrink: 0; }

/* Main */
#main { flex: 1; min-height: 0; display: flex; overflow: hidden; }

/* Product/Item panel */
#panel-products {
  display: grid; grid-template-rows: auto auto 1fr;
  flex: 1; min-height: 0; overflow: hidden; background: #f5f6fa;
}
#product-toolbar {
  padding: 10px 14px; background: #fff; border-bottom: 1px solid #e8eaf0;
  display: flex; gap: 8px; align-items: center;
}
#prod-search-wrap { position: relative; flex: 1; }
#prod-search-wrap i { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #9ca3af; pointer-events: none; }
#prod-search { width: 100%; border: 1px solid #e2e8f0; border-radius: 8px;
               padding: 7px 10px 7px 30px; font-size: .85rem; background: #f8f9fb; }
#prod-search:focus { outline: none; border-color: var(--accent); }
#prod-cat { border: 1px solid #e2e8f0; border-radius: 8px; padding: 7px 10px; font-size: .85rem; background: #f8f9fb; }
#cat-tabs { display: flex; gap: 6px; padding: 8px 14px; overflow-x: auto; background: #fff; border-bottom: 1px solid #e8eaf0; }
.cat-tab { padding: 4px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600;
           cursor: pointer; white-space: nowrap; border: 1.5px solid #e2e8f0;
           background: #f8f9fb; color: #6b7280; transition: .15s; }
.cat-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
#product-grid {
  flex: 1; min-height: 0; overflow-y: auto; padding: 14px;
  display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  grid-auto-rows: auto; gap: 10px; align-content: start;
  touch-action: pan-y;
}
.prod-card {
  background: #fff; border: 2px solid #edf0f7; border-radius: 12px;
  padding: 14px 10px 12px; text-align: center; cursor: pointer;
  transition: border-color .15s, transform .1s; user-select: none;
  position: relative;
}
.prod-card:hover  { border-color: var(--accent); }
.prod-card:active { transform: scale(.95); }
.pc-name  { font-size: 1rem; font-weight: 700; line-height: 1.35; color: #1e2235; }
.pc-sub   { font-size: .72rem; color: #9ca3af; margin-top: 4px; }
.pc-price { font-size: 1rem; font-weight: 800; color: var(--accent); margin-top: 6px; }
.pc-custom-badge {
  position: absolute; top: 6px; right: 8px;
  color: #6b7280; font-size: .72rem;
}

/* Cart panel */
#panel-cart { flex: 0 0 var(--cart-w); display: flex; flex-direction: column; overflow: hidden; background: #fff; border-left: 1px solid #e8eaf0; }
#cart-header { flex-shrink: 0; padding: 12px 16px; border-bottom: 1px solid #edf0f7;
               display: flex; align-items: center; justify-content: space-between; }
#cart-header h6 { font-size: .92rem; font-weight: 700; margin: 0; }
#cart-count { background: var(--accent); color: #fff; border-radius: 20px; font-size: .72rem; font-weight: 700; padding: 1px 8px; margin-left: 6px; }
#cart-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #9ca3af; gap: 8px; font-size: .88rem; }
#cart-empty.hidden { visibility: hidden; }
#cart-empty i { font-size: 2.5rem; opacity: .35; }
#cart-items { flex: 0 1 auto; min-height: 0; overflow-y: auto; padding: 0 12px; touch-action: pan-y; }
.cart-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }
.cart-row:last-child { border-bottom: none; }
.cart-info { flex: 1; min-width: 0; }
.cart-name    { font-size: .85rem; font-weight: 600; color: #1e2235; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cart-options { font-size: .7rem; color: #6366f1; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cart-sku     { font-size: .7rem; color: #9ca3af; }
.cart-qty-ctrl { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.qty-btn { width: 30px; height: 30px; border-radius: 8px; border: 1.5px solid #e2e8f0; background: #f8f9fb; font-size: 1rem; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: .1s; font-weight: 600; }
.qty-btn:hover { background: #e8eaf0; }
.qty-val { min-width: 28px; text-align: center; font-weight: 700; font-size: .88rem; }
.cart-price { font-size: .88rem; font-weight: 800; color: var(--accent); min-width: 72px; text-align: right; flex-shrink: 0; }
.cart-del { color: #d1d5db; cursor: pointer; font-size: 1rem; padding: 4px; border-radius: 6px; transition: color .1s; flex-shrink: 0; }
.cart-del:hover { color: #ef4444; }
#cart-footer { flex-shrink: 0; padding: 14px 16px; border-top: 2px solid #f3f4f6; background: #fff; }
.cf-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cf-label { font-size: .83rem; color: #6b7280; }
.cf-val   { font-size: .83rem; font-weight: 600; }
#cf-total-row { padding: 10px 0; border-top: 1.5px dashed #e2e8f0; margin-top: 4px; }
#cf-total { font-size: 1.6rem; font-weight: 900; color: var(--accent); }
#btn-checkout { width: 100%; padding: 14px; font-size: 1rem; font-weight: 800;
                border-radius: 12px; background: var(--accent); color: #fff; border: none;
                cursor: pointer; transition: background .15s; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 10px; }
#btn-checkout:hover { background: var(--accent-dark); }
#btn-checkout:disabled { background: #9ca3af; cursor: not-allowed; }

/* Modal backdrop */
.modal-backdrop-custom { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1050; display: flex; align-items: center; justify-content: center; }
.modal-box-sm { background: #fff; border-radius: 12px; width: 360px; max-width: 95vw; box-shadow: 0 20px 60px rgba(0,0,0,.3); }

/* 客製化 Modal */
.modal-box-custom {
  background: #fff; border-radius: 14px;
  width: 460px; max-width: 95vw;
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.og-section { margin-bottom: 20px; }
.og-title {
  font-size: .88rem; font-weight: 700; color: #1e2235;
  margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.og-badge {
  font-size: .65rem; font-weight: 700; padding: 2px 7px; border-radius: 20px;
}
.og-badge.required { background: #fee2e2; color: #dc2626; }
.og-badge.multi    { background: #e0e7ff; color: #4f46e5; }
.og-choices { display: flex; flex-wrap: wrap; gap: 8px; }
.choice-pill {
  padding: 6px 14px; border-radius: 20px; font-size: .82rem; font-weight: 600;
  border: 2px solid #e2e8f0; background: #f8f9fb; color: #374151;
  cursor: pointer; transition: all .15s; user-select: none;
  display: flex; align-items: center; gap: 4px;
}
.choice-pill:hover { border-color: var(--accent); color: var(--accent); }
.choice-pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.choice-extra { font-size: .72rem; opacity: .85; }

.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #e9ecef; }
.modal-title  { font-size: 1rem; font-weight: 600; margin: 0; }
.modal-body   { padding: 18px; }
.modal-footer { padding: 12px 18px; border-top: 1px solid #e9ecef; display: flex; gap: 8px; justify-content: flex-end; }
</style>
