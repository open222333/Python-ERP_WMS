<!-- [U10] 自 views/OrderView.vue 拆出 -->
<script setup lang="ts">
import { rowPrice, type CartRow } from './orderCart'

defineProps<{ cart: CartRow[] }>()
const emit = defineEmits<{
  (e: 'change-qty', idx: number, delta: number): void
  (e: 'remove', idx: number): void
}>()
</script>

<template>
  <div v-for="(row, idx) in cart" :key="idx" class="cart-row">
    <div class="cr-info">
      <div class="cr-name">{{ row.item.name }}</div>
      <div v-if="row.selections.length" class="cr-opts">
        {{ row.selections.map(s => s.choice_name).join(' · ') }}
      </div>
      <div class="cr-price">NT${{ rowPrice(row) }}</div>
    </div>
    <div class="cr-qty">
      <button :aria-label="`減少 ${row.item.name}`" @click="emit('change-qty', idx, -1)">－</button>
      <span>{{ row.qty }}</span>
      <button :aria-label="`增加 ${row.item.name}`" @click="emit('change-qty', idx, 1)">＋</button>
    </div>
    <button class="cr-del" @click="emit('remove', idx)" aria-label="移除" title="移除">
      <i class="bi bi-x"></i>
    </button>
  </div>
</template>

<style scoped>
/* ── 共用 Cart Row ─────────────────────────────── */
.cart-row {
  display: flex;
  align-items: center;
  gap: .4rem;
  padding: .5rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.cr-info  { flex: 1; min-width: 0; }
.cr-name  { font-weight: 600; font-size: .85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cr-opts  { font-size: .7rem; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cr-price { font-size: .78rem; color: #3b82f6; font-weight: 600; }
.cr-qty   { display: flex; align-items: center; gap: .2rem; flex-shrink: 0; }
.cr-qty button {
  width: 1.5rem; height: 1.5rem;
  border: 1px solid #e2e8f0; border-radius: 4px;
  background: #f8fafc; font-size: .85rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.cr-qty span { font-weight: 700; font-size: .82rem; min-width: 1.2rem; text-align: center; }
.cr-del {
  background: none; border: none; color: #94a3b8;
  cursor: pointer; font-size: 1.1rem; padding: .1rem; line-height: 1;
  flex-shrink: 0;
}
.cr-del:hover { color: #ef4444; }

/* [MOBILE] 觸控裝置：購物車加減鈕加大（原 24px 太小） */
@media (pointer: coarse) {
  .cr-qty { gap: .35rem; }
  .cr-qty button { width: 2.25rem; height: 2.25rem; font-size: 1.05rem; border-radius: 8px; }
  .cr-del { padding: .45rem; font-size: 1.25rem; }
}
</style>
