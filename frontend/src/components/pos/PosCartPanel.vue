<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- Right: Cart -->
  <div id="panel-cart">
    <div id="cart-header">
      <div>
        <h6 style="display:inline"><i class="bi bi-cart3 me-1"></i>購物車</h6>
        <span v-if="cart.length" id="cart-count">{{ cartTotal.count }}</span>
      </div>
      <button class="tb-btn danger" style="padding:4px 10px;font-size:.75rem" @click="emit('clear')">
        <i class="bi bi-trash"></i>清空
      </button>
    </div>

    <div id="cart-empty" :class="{ hidden: cart.length > 0 }">
      <i class="bi bi-cart-x"></i>
      <span>購物車空空如也</span>
    </div>

    <div id="cart-items">
      <div v-for="(row, idx) in cart" :key="idx" class="cart-row">
        <div class="cart-info"
             :class="{ 'cart-info-editable': isMenuMode && row.item.applied_groups?.length }"
             @click="emit('edit-item', idx)">
          <div class="cart-name">
            {{ row.item.name }}
            <i v-if="isMenuMode && row.item.applied_groups?.length"
               class="bi bi-pencil-square cart-edit-icon"></i>
          </div>
          <div v-if="row.selections?.length" class="cart-options">
            {{ row.selections.map((s: any) => s.choice_name).join(' · ') }}
          </div>
          <div v-else class="cart-sku">{{ row.item.sku || '' }}</div>
        </div>
        <div class="cart-qty-ctrl">
          <button class="qty-btn" @click="emit('change-qty', idx, -1)">－</button>
          <span class="qty-val qty-val-click" @click.stop="emit('open-qty-numpad', idx)">{{ row.quantity }}</span>
          <button class="qty-btn" @click="emit('change-qty', idx, 1)">＋</button>
        </div>
        <div class="cart-price">NT$ {{ rowPrice(row) * row.quantity }}</div>
        <i class="bi bi-x-circle cart-del" @click="emit('remove', idx)"></i>
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
          <input v-model.number="discountModel" type="number" min="0" step="1"
                 style="width:80px;border:1.5px solid #e2e8f0;border-radius:7px;padding:4px 8px;text-align:right;font-size:.85rem;font-weight:600" />
        </div>
      </div>
      <div v-if="discountPresets.length && cart.length" class="disc-presets">
        <button v-for="p in discountPresets" :key="p.label"
                class="disc-btn"
                @click="emit('apply-preset', p)">
          {{ p.label }}
        </button>
      </div>
      <div class="cf-row" id="cf-total-row">
        <span id="cf-total-lbl">合計</span>
        <span id="cf-total">NT$ {{ cartTotal.total }}</span>
      </div>
      <button id="btn-checkout" :disabled="cart.length === 0" @click="emit('checkout')">
        <i class="bi bi-credit-card-2-front-fill" style="font-size:1.1rem"></i>結帳
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CartRow } from './types'

const props = defineProps<{
  cart:            CartRow[]
  discount:        number
  discountPresets: { label: string; type: 'percent'|'fixed'; value: number }[]
  isMenuMode:      boolean
  cartTotal:       { subtotal: number; total: number; count: number }
  rowPrice:        (row: CartRow) => number
}>()

const emit = defineEmits<{
  (e: 'update:discount', v: number): void
  (e: 'clear'): void
  (e: 'edit-item', idx: number): void
  (e: 'change-qty', idx: number, delta: number): void
  (e: 'open-qty-numpad', idx: number): void
  (e: 'remove', idx: number): void
  (e: 'apply-preset', p: { label: string; type: 'percent'|'fixed'; value: number }): void
  (e: 'checkout'): void
}>()

const discountModel = computed({
  get: () => props.discount,
  set: v => emit('update:discount', v),
})
</script>

<style scoped>
/* Cart panel */
#panel-cart { flex: none; width: var(--cart-ratio); min-width: 260px; display: flex; flex-direction: column; overflow: hidden; background: #fff; border-left: 1px solid #e8eaf0; }
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
.disc-presets { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
.disc-btn {
  padding: 3px 10px; font-size: .75rem; font-weight: 600;
  border: 1.5px solid #6366f1; border-radius: 20px;
  background: #fff; color: #6366f1; cursor: pointer; transition: all .15s;
}
.disc-btn:hover { background: #6366f1; color: #fff; }
#cf-total-row { padding: 10px 0; border-top: 1.5px dashed #e2e8f0; margin-top: 4px; }
#cf-total { font-size: 1.6rem; font-weight: 900; color: var(--accent); }
#btn-checkout { width: 100%; padding: 14px; font-size: 1rem; font-weight: 800;
                border-radius: 12px; background: var(--accent); color: #fff; border: none;
                cursor: pointer; transition: background .15s; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 10px; }
#btn-checkout:hover { background: var(--accent-dark); }
#btn-checkout:disabled { background: #9ca3af; cursor: not-allowed; }

/* ── 購物車品項可編輯 ── */
.cart-info-editable { cursor: pointer; }
.cart-info-editable:hover .cart-name { color: #6366f1; }
.cart-edit-icon { font-size: .65rem; color: #9ca3af; margin-left: 4px; vertical-align: middle; }
.qty-val-click { cursor: pointer; text-decoration: underline dotted #9ca3af; min-width: 1.8rem; text-align: center; }
.qty-val-click:hover { color: #6366f1; text-decoration-color: #6366f1; }

/* [REFACTOR] .tb-btn 樣式複製自 PosView.vue Topbar 區塊（清空按鈕使用） */
.tb-btn { background: #2c3148; border: 1px solid #3d4566; color: #cbd5e1;
          border-radius: 7px; padding: 5px 10px; font-size: .78rem; cursor: pointer;
          display: flex; align-items: center; gap: 5px; white-space: nowrap; transition: background .15s; }
.tb-btn:hover { background: #3a4060; }
.tb-btn.danger { border-color: #7f1d1d; color: #fca5a5; }
.tb-btn.danger:hover { background: #7f1d1d; }
</style>
