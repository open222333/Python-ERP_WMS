<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- ── 數量 Numpad Modal ──────────────────────────── -->
  <Teleport to="body">
    <div class="modal-backdrop-custom" @click.self="emit('close')">
      <div class="modal-box-numpad">
        <div class="modal-header">
          <h5 class="modal-title"><i class="bi bi-123 me-1"></i>輸入數量</h5>
          <button class="btn-close" @click="emit('close')"></button>
        </div>
        <div class="modal-body p-3">
          <div class="qty-numpad-display">{{ qtyNumpadStr }}</div>
          <div class="qty-numpad-grid">
            <button v-for="d in ['7','8','9','4','5','6','1','2','3']" :key="d"
                    class="np-btn" @click="qtyNumpadPress(d)">{{ d }}</button>
            <button class="np-btn np-clear" @click="qtyNumpadStr = ''">C</button>
            <button class="np-btn" @click="qtyNumpadPress('0')">0</button>
            <button class="np-btn np-back" @click="qtyNumpadBack">⌫</button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="emit('close')">取消</button>
          <button class="btn btn-primary fw-bold px-4" @click="emit('confirm', qtyNumpadStr)">確認</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', str: string): void
}>()

// 預設空白，未輸入就維持原數量（原 openQtyNumpad 內重設邏輯）
const qtyNumpadStr = ref('')

function qtyNumpadPress(d: string) {
  const next = qtyNumpadStr.value + d
  if (next.length <= 4) qtyNumpadStr.value = next
}

function qtyNumpadBack() {
  qtyNumpadStr.value = qtyNumpadStr.value.slice(0, -1)  // 退到空字串即停
}
</script>

<style scoped>
/* Modal backdrop（複製自 PosView.vue 共用樣式） */
.modal-backdrop-custom { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1050; display: flex; align-items: center; justify-content: center; overflow-y: auto; padding: 16px; }

.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #e9ecef; }
.modal-title  { font-size: 1rem; font-weight: 600; margin: 0; }
.modal-body   { padding: 18px; }
.modal-footer { padding: 12px 18px; border-top: 1px solid #e9ecef; display: flex; gap: 8px; justify-content: flex-end; }

/* [REFACTOR] .np-btn 第一段（原 PosView Cash Numpad 區塊）——
   原檔中兩段 .np-btn 同時作用於本 Modal，需保留先後順序以維持外觀 */
.np-btn {
  padding: 13px 0; border-radius: 9px; font-size: 1.1rem; font-weight: 600;
  border: 1.5px solid #e2e8f0; background: #fff; color: #1e2235;
  cursor: pointer; transition: .1s; text-align: center; line-height: 1;
}
.np-btn:hover  { background: #f0f4ff; border-color: var(--accent); }
.np-btn:active { transform: scale(.92); }
.np-btn.np-util  { background: #f3f4f6; font-size: .95rem; color: #374151; }
.np-btn.np-clear { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.np-btn.np-clear:hover { background: #fecaca; }
.np-btn.np-zero { grid-column: span 3; }

/* ── 數量 Numpad Modal ── */
.modal-box-numpad {
  background: #fff;
  border-radius: 14px;
  width: min(280px, 90vw);
  box-shadow: 0 8px 32px rgba(0,0,0,.18);
  overflow: hidden;
}
.qty-numpad-display {
  font-size: 2rem;
  font-weight: 700;
  text-align: right;
  padding: .5rem 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: .75rem;
  background: #f8fafc;
  min-height: 3.2rem;
  letter-spacing: .05em;
}
.qty-numpad-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: .35rem;
}
/* [REFACTOR] .np-btn 第二段（原 PosView 檔尾區塊，覆蓋第一段部分屬性） */
.np-btn {
  padding: .7rem;
  font-size: 1.15rem;
  font-weight: 600;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: background .1s;
  color: #1e2235;
}
.np-btn:active { background: #e0e7ff; }
.np-clear { color: #ef4444; }
.np-back  { color: #6366f1; font-size: 1.1rem; }
</style>
