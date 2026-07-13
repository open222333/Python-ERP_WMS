<template>
  <!-- 直向提示 -->
  <div id="rotate-hint">
    <i class="bi bi-phone-landscape"></i>
    <div style="font-size:1.1rem;font-weight:600">請旋轉裝置為橫向使用</div>
    <div style="font-size:.85rem;color:#94a3b8">POS 收銀系統需要橫向模式</div>
  </div>

  <div id="pos-root">
    <!-- ── Topbar ── [REFACTOR] 拆出至 components/pos/PosTopbar.vue -->
    <PosTopbar
      v-model:warehouse="selectedWarehouse"
      v-model:menu="selectedMenu"
      :warehouses="warehouses"
      :menus="menus"
      :products="products"
      @add-product="p => commitToCart(p, [])"
      @show-history="showHistory = true"
    />

    <!-- ── Main ──────────────────────────────────────── -->
    <div id="main">
      <!-- Left: Items ── [REFACTOR] 拆出至 components/pos/PosProductPanel.vue -->
      <PosProductPanel
        :selected-menu="selectedMenu"
        :menus="menus"
        @item-click="handleItemClick"
      />

      <!-- Right: Cart ── [REFACTOR] 拆出至 components/pos/PosCartPanel.vue -->
      <PosCartPanel
        :cart="cart"
        v-model:discount="discount"
        :discount-presets="discountPresets"
        :is-menu-mode="isMenuMode"
        :cart-total="cartTotal"
        :row-price="rowPrice"
        @edit-item="editCartItem"
        @change-qty="changeQty"
        @open-qty-numpad="openQtyNumpad"
        @remove="removeCart"
        @clear="clearCart"
        @apply-preset="applyPreset"
        @checkout="showPayment = true"
      />
    </div>
  </div>

  <!-- Toast area -->
  <AppToast />

  <!-- ── 客製化選項 Modal ── [REFACTOR] 拆出至 components/pos/PosCustomizeModal.vue -->
  <PosCustomizeModal
    v-if="showCustomModal"
    :target="customTarget"
    :initial-selections="customSelections"
    :is-edit="customCartIdx !== null"
    @close="showCustomModal = false"
    @confirm="onCustomConfirm"
  />

  <!-- ── 數量 Numpad Modal ── [REFACTOR] 拆出至 components/pos/PosQtyNumpadModal.vue -->
  <PosQtyNumpadModal
    v-if="showQtyNumpad"
    @close="showQtyNumpad = false"
    @confirm="onQtyNumpadConfirm"
  />

  <!-- ── Payment Modal ── [REFACTOR] 拆出至 components/pos/PosPaymentModal.vue -->
  <PosPaymentModal
    v-model:show="showPayment"
    :cart="cart"
    :cart-total="cartTotal"
    :discount="discount"
    :selected-warehouse="selectedWarehouse"
    :pay-methods="payMethods"
    :invoice-enabled="invoiceEnabled"
    :inv-auto-issue="invAutoIssue"
    :row-price="rowPrice"
    @success="clearCart"
  />

  <!-- ── 今日銷售記錄 Modal ── [REFACTOR] 拆出至 components/pos/PosHistoryModal.vue -->
  <PosHistoryModal v-model:show="showHistory" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import AppToast from '@/components/AppToast.vue'
// [REFACTOR] 自 PosView.vue 拆出的子元件
import PosTopbar from '@/components/pos/PosTopbar.vue'
import PosProductPanel from '@/components/pos/PosProductPanel.vue'
import PosCartPanel from '@/components/pos/PosCartPanel.vue'
import PosCustomizeModal from '@/components/pos/PosCustomizeModal.vue'
import PosQtyNumpadModal from '@/components/pos/PosQtyNumpadModal.vue'
import PosPaymentModal from '@/components/pos/PosPaymentModal.vue'
import PosHistoryModal from '@/components/pos/PosHistoryModal.vue'
// [REFACTOR] 共用型別拆出至 components/pos/types.ts
import type { SelectionItem, CartRow } from '@/components/pos/types'

const toast = useToastStore()

// ── State ─────────────────────────────────────────
const products   = ref<any[]>([])
const categories = ref<any[]>([])
const warehouses = ref<any[]>([])
const menus      = ref<any[]>([])
const payMethods = ref<any[]>([{ id: 'cash', label: '現金', enabled: true, has_cash: true }])

const selectedWarehouse = ref('')
const selectedMenu      = ref('')

const cart              = ref<CartRow[]>([])
const discount          = ref(0)
const discountPresets   = ref<{label:string; type:'percent'|'fixed'; value:number}[]>([])

const showPayment       = ref(false)
const showHistory       = ref(false)

// 電子發票啟用狀態（傳入 PosPaymentModal）
const invoiceEnabled = ref(false)
const invAutoIssue   = ref(false)

// ── 客製化 Modal ──────────────────────────────────
const showCustomModal  = ref(false)
const customTarget     = ref<any>(null)
const customSelections = ref<Record<string, string[]>>({})
const customCartIdx    = ref<number | null>(null)  // null = 不使用（已改為點購物車品項才開）

// ── 數量 Numpad ───────────────────────────────────
const showQtyNumpad = ref(false)
const qtyNumpadIdx  = ref<number | null>(null)

// ── Computed ──────────────────────────────────────
const isMenuMode = computed(() => !!selectedMenu.value)

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

// ── Methods ───────────────────────────────────────
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
  // 直接加入購物車（套用預設選項），點購物車品項才開客製化 Modal
  const groups: any[] = item.applied_groups || []
  const selections: SelectionItem[] = []
  if (isMenuMode.value && groups.length > 0) {
    for (const grp of groups) {
      const defaults = (grp.choices || []).filter((c: any) => c.is_default)
      for (const ch of defaults) {
        selections.push({
          group_id: grp._id, group_name: grp.name,
          choice_id: ch._id, choice_name: ch.name, extra_price: ch.extra_price || 0,
        })
      }
    }
  }
  commitToCart(item, selections)
}

function editCartItem(idx: number) {
  const row = cart.value[idx]
  const groups: any[] = row.item.applied_groups || []
  if (!isMenuMode.value || !groups.length) return
  customTarget.value  = row.item
  customCartIdx.value = idx
  const sel: Record<string, string[]> = {}
  for (const grp of groups) {
    sel[grp._id] = row.selections
      .filter((s: SelectionItem) => s.group_id === grp._id)
      .map((s: SelectionItem) => s.choice_id)
  }
  customSelections.value = sel
  showCustomModal.value  = true
}

// [REFACTOR] 原 confirmCustom() 的購物車寫入部分（選項驗證與組裝移至 PosCustomizeModal）
function onCustomConfirm(selections: SelectionItem[]) {
  if (customCartIdx.value !== null) {
    cart.value[customCartIdx.value].selections = selections
    customCartIdx.value = null
  } else {
    commitToCart(customTarget.value, selections)
  }
  showCustomModal.value = false
}

function openQtyNumpad(idx: number) {
  qtyNumpadIdx.value  = idx
  showQtyNumpad.value = true  // Numpad 輸入內容由 PosQtyNumpadModal 自行管理（掛載時重設為空白）
}

// [REFACTOR] 原 qtyNumpadConfirm()：套用 Numpad 輸入的數量
function onQtyNumpadConfirm(str: string) {
  if (str !== '' && qtyNumpadIdx.value !== null) {
    const qty = parseInt(str) || 0
    if (qty <= 0) cart.value.splice(qtyNumpadIdx.value, 1)
    else          cart.value[qtyNumpadIdx.value].quantity = qty
  }
  showQtyNumpad.value = false
  qtyNumpadIdx.value  = null
}

function changeQty(idx: number, delta: number) {
  cart.value[idx].quantity += delta
  if (cart.value[idx].quantity <= 0) cart.value.splice(idx, 1)
}

function removeCart(idx: number) { cart.value.splice(idx, 1) }
function clearCart() { cart.value = []; discount.value = 0 }

function applyPreset(p: {type: 'percent'|'fixed'; value: number}) {
  const sub = cartTotal.value.subtotal
  if (p.type === 'percent') {
    discount.value = Math.round(sub * (1 - p.value / 100))
  } else {
    discount.value = Math.min(p.value, sub)
  }
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
    // [REFACTOR] 預設付款方式改由 PosPaymentModal（usePosPayment）watch payMethods 設定

    // ── 電子發票啟用狀態 ────────────────────────
    try {
      const ir = await http.get('/invoice/settings')
      const is = ir.data?.data || {}
      invoiceEnabled.value = !!is.enabled
      invAutoIssue.value   = !!is.auto_issue
    } catch { /* 忽略，發票功能可選 */ }

    // ── 套用系統設定預設值 ──────────────────────
    const s = sr.data?.data || {}
    if (s.default_warehouse_id) {
      const wh = (warehouses.value as any[]).find((w: any) => w._id === s.default_warehouse_id)
      if (wh) selectedWarehouse.value = s.default_warehouse_id
    }
    discountPresets.value = s.pos_discount_presets || []
    if (s.pos_default_menu_id) {
      const m = (menus.value as any[]).find((m: any) => m._id === s.pos_default_menu_id)
      if (m) {
        selectedMenu.value = s.pos_default_menu_id
        // [REFACTOR] 原 onMenuChange()：分類/搜尋重設改由 PosProductPanel watch selectedMenu 處理
      }
    }
  } catch {
    toast.show('載入商品失敗', 'danger')
  }
}

onMounted(() => {
  // [REFACTOR] 時鐘與掃描框 focus 移至 PosTopbar
  boot()
})
</script>

<style scoped>
:root {
  --accent:      #4f6ef7;
  --accent-dark: #3a56d4;
  --topbar-h:    56px;
  --cart-ratio:  36%;
}

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

/* Main */
#main { flex: 1; min-height: 0; display: flex; overflow: hidden; }
</style>
