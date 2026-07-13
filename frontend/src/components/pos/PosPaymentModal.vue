<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- ── Payment Modal ─────────────────────────────── -->
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop-custom" @click.self="close()">
      <div class="modal-box-sm">
        <div class="modal-header">
          <h5 class="modal-title"><i class="bi bi-credit-card me-1"></i>付款</h5>
          <button class="btn-close" @click="close()"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3 text-center">
            <div v-if="discount > 0" class="d-flex justify-content-between px-3 text-muted small mb-1">
              <span>小計</span><span>NT$ {{ cartTotal.subtotal }}</span>
            </div>
            <div v-if="discount > 0" class="d-flex justify-content-between px-3 small mb-1 text-danger fw-semibold">
              <span>折扣</span><span>- NT$ {{ discount }}</span>
            </div>
            <div class="text-muted small">應付金額</div>
            <div class="fs-2 fw-bold text-primary">NT$ {{ cartTotal.total }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">付款方式</label>
            <div class="d-flex flex-wrap gap-1">
              <button v-for="pm in enabledPayMethods" :key="pm.id"
                      class="btn btn-sm" :class="selectedPayMethod === pm.id ? 'btn-primary' : 'btn-outline-secondary'"
                      @click="selectPayMethod(pm.id)">{{ pm.label }}</button>
            </div>
          </div>
          <!-- Cash numpad -->
          <div v-if="currentPayHasCash" class="numpad-section">
            <!-- Display row -->
            <div class="numpad-display">
              <div>
                <div class="numpad-label">收現</div>
                <div class="numpad-amount">NT$&nbsp;{{ cashReceived }}</div>
              </div>
              <button class="numpad-exact-btn" @click="fillExact">符合金額</button>
            </div>

            <!-- +/- toggle + denomination row -->
            <div class="denom-row">
              <button class="mode-toggle-btn" :class="denomMode === '+' ? 'plus-mode' : 'minus-mode'"
                      @click="denomMode = denomMode === '+' ? '-' : '+'">{{ denomMode }}</button>
              <button v-for="d in [1000, 500, 100, 50]" :key="d" class="denom-btn" @click="addDenom(d)">
                {{ d }}
              </button>
            </div>

            <!-- Numpad grid -->
            <div class="numpad-grid">
              <button class="np-btn" @click="numpadPress('7')">7</button>
              <button class="np-btn" @click="numpadPress('8')">8</button>
              <button class="np-btn" @click="numpadPress('9')">9</button>
              <button class="np-btn np-util" @click="numpadBack">⌫</button>

              <button class="np-btn" @click="numpadPress('4')">4</button>
              <button class="np-btn" @click="numpadPress('5')">5</button>
              <button class="np-btn" @click="numpadPress('6')">6</button>
              <button class="np-btn np-clear" @click="numpadClear">C</button>

              <button class="np-btn" @click="numpadPress('1')">1</button>
              <button class="np-btn" @click="numpadPress('2')">2</button>
              <button class="np-btn" @click="numpadPress('3')">3</button>
              <button class="np-btn np-util" @click="numpadPress('00')">00</button>

              <button class="np-btn np-zero" @click="numpadPress('0')">0</button>
            </div>

            <!-- Change row -->
            <div class="numpad-change-row">
              <span class="change-label">找零</span>
              <span class="change-amount" :class="{ insufficient: changeAmt < 0 }">NT$ {{ changeAmt }}</span>
            </div>
          </div>
          <!-- LINE Pay 掃描顧客條碼 -->
          <div v-if="isLinePayMode" class="mb-2">
            <label class="form-label small fw-semibold">
              <i class="bi bi-upc-scan me-1 text-success"></i>
              顧客{{ selectedPayMethod === 'zpay' ? '全支付' : 'LINE Pay' }}付款條碼
            </label>
            <div class="inv-scan-wrap" :class="{ 'inv-scan-ok': linePayKey }">
              <i class="bi bi-qr-code inv-scan-icon text-success"></i>
              <input ref="linePayScanRef" v-model="linePayKey" type="text"
                     class="inv-scan-input"
                     :placeholder="selectedPayMethod === 'zpay'
                       ? '請掃描顧客全支付 App 出示的條碼…'
                       : '請掃描顧客 LINE Pay 出示的付款條碼…'" />
              <button v-if="linePayKey" class="inv-clear-btn" @click="linePayKey = ''">
                <i class="bi bi-x-circle"></i>
              </button>
            </div>
            <div v-if="linePayKey" class="inv-detected mt-1">
              <span class="badge bg-success">
                <i class="bi bi-check-circle me-1"></i>已讀取付款碼
              </span>
              <span class="inv-detected-num">{{ linePayKey.slice(0, 6) }}•••</span>
            </div>
            <div v-else class="form-text text-muted">
              <template v-if="selectedPayMethod === 'zpay'">
                請顧客開啟全支付 App → 付款 → 出示條碼，再以掃描器讀取
              </template>
              <template v-else>
                請顧客開啟 LINE Pay → 付款 → 出示條碼，再以掃描器讀取
              </template>
            </div>
          </div>
          <div class="mb-2">
            <label class="form-label small fw-semibold">備註</label>
            <input v-model="payRemark" type="text" class="form-control form-control-sm" placeholder="選填" />
          </div>
          <!-- 電子發票 -->
          <div v-if="invoiceEnabled" class="inv-section">
            <div class="inv-header">
              <span class="fw-semibold small">
                <i class="bi bi-receipt-cutoff me-1 text-primary"></i>電子發票
              </span>
              <div class="d-flex gap-1">
                <button class="inv-mode-btn" :class="{ active: invMode === 'none' }" @click="setInvMode('none')">不開立</button>
                <button class="inv-mode-btn" :class="{ active: invMode === 'scan' }" @click="setInvMode('scan')">
                  <i class="bi bi-upc-scan"></i> 載具
                </button>
                <button class="inv-mode-btn" :class="{ active: invMode === 'tax'  }" @click="setInvMode('tax')">統編</button>
                <button class="inv-mode-btn" :class="{ active: invMode === 'love' }" @click="setInvMode('love')">捐贈</button>
              </div>
            </div>

            <!-- 掃描載具條碼 -->
            <div v-if="invMode === 'scan'" class="mt-2">
              <div class="inv-scan-wrap" :class="{ 'inv-scan-ok': !!invCarrierType }">
                <i class="bi bi-upc-scan inv-scan-icon"></i>
                <input ref="invScanRef" v-model="invScanRaw" type="text"
                       class="inv-scan-input" placeholder="掃描或輸入載具條碼，按 Enter 確認"
                       @keydown.enter="onInvScan" @input="onInvInput" />
                <button v-if="invScanRaw" class="inv-clear-btn" @click="clearInvScan">
                  <i class="bi bi-x-circle"></i>
                </button>
              </div>
              <div v-if="invCarrierType" class="inv-detected">
                <span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>{{ invCarrierType }}</span>
                <span class="inv-detected-num font-monospace">{{ invNum }}</span>
              </div>
              <div v-else class="form-text mt-1 text-muted">
                手機條碼 /XXXXXXX（8碼）・自然人憑證（16碼英數）
              </div>
            </div>

            <!-- 統一編號 -->
            <div v-if="invMode === 'tax'" class="mt-2">
              <div class="input-group input-group-sm">
                <span class="input-group-text"><i class="bi bi-building"></i></span>
                <input v-model="invBuyerId" type="text" maxlength="8"
                       class="form-control font-monospace" placeholder="統一編號（8碼數字）"
                       @input="invBuyerId = invBuyerId.replace(/\D/g, '')" />
                <span class="input-group-text" :class="invBuyerId.length === 8 ? 'text-success' : 'text-muted'">
                  <i class="bi" :class="invBuyerId.length === 8 ? 'bi-check-lg' : 'bi-dash'"></i>
                </span>
              </div>
              <div class="form-text">開立三聯式發票需填買方統一編號</div>
            </div>

            <!-- 愛心碼 -->
            <div v-if="invMode === 'love'" class="mt-2">
              <div class="input-group input-group-sm">
                <span class="input-group-text text-danger"><i class="bi bi-heart-fill"></i></span>
                <input v-model="invLoveCode" type="text" class="form-control" placeholder="輸入愛心碼" />
              </div>
              <div class="form-text">發票金額將捐贈給指定公益團體</div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="close()">取消</button>
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
import { usePosPayment } from './usePosPayment'
import type { CartRow } from './types'

const props = defineProps<{
  show:              boolean
  cart:              CartRow[]
  cartTotal:         { subtotal: number; total: number; count: number }
  discount:          number
  selectedWarehouse: string
  payMethods:        any[]
  invoiceEnabled:    boolean
  invAutoIssue:      boolean
  rowPrice:          (row: CartRow) => number
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'success'): void
}>()

// [REFACTOR] 付款 / 發票 / LINE Pay / 結帳邏輯拆出至 usePosPayment.ts
const {
  selectedPayMethod, cashReceived, changeAmt, payRemark, checkoutLoading,
  enabledPayMethods, currentPayHasCash,
  denomMode, numpadPress, numpadBack, numpadClear, addDenom, fillExact,
  invMode, invScanRaw, invNum, invCarrierType, invBuyerId, invLoveCode, invScanRef,
  setInvMode, onInvInput, onInvScan, clearInvScan,
  linePayKey, linePayScanRef, isLinePayMode,
  selectPayMethod, confirmCheckout,
} = usePosPayment(props, emit)

function close() { emit('update:show', false) }
</script>

<style scoped>
/* Modal backdrop（複製自 PosView.vue 共用樣式） */
.modal-backdrop-custom { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1050; display: flex; align-items: center; justify-content: center; overflow-y: auto; padding: 16px; }
.modal-box-sm { background: #fff; border-radius: 12px; width: 420px; max-width: 95vw; box-shadow: 0 20px 60px rgba(0,0,0,.3); max-height: calc(100vh - 32px); display: flex; flex-direction: column; }
.modal-box-sm .modal-body { overflow-y: auto; flex: 1 1 auto; }

/* 電子發票區塊 */
.inv-section {
  border-top: 1px solid #e9ecef;
  padding-top: 12px;
  margin-top: 8px;
}
.inv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.inv-mode-btn {
  padding: 3px 10px;
  border-radius: 20px;
  font-size: .72rem;
  font-weight: 600;
  border: 1.5px solid #e2e8f0;
  background: #f8f9fb;
  color: #6b7280;
  cursor: pointer;
  transition: .15s;
  white-space: nowrap;
}
.inv-mode-btn:hover { border-color: var(--accent); color: var(--accent); }
.inv-mode-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }

.inv-scan-wrap {
  display: flex;
  align-items: center;
  background: #f8f9fb;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 10px;
  gap: 8px;
  transition: border-color .15s;
}
.inv-scan-wrap:focus-within { border-color: var(--accent); background: #fff; }
.inv-scan-wrap.inv-scan-ok  { border-color: #22c55e; background: #f0fdf4; }
.inv-scan-icon { color: #9ca3af; font-size: 1rem; flex-shrink: 0; }
.inv-scan-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px 4px;
  font-size: .85rem;
  font-family: monospace;
  outline: none;
}
.inv-clear-btn {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  font-size: .9rem;
  line-height: 1;
}
.inv-clear-btn:hover { color: #ef4444; }
.inv-detected {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.inv-detected-num {
  font-size: .78rem;
  color: #6b7280;
  letter-spacing: .5px;
}

.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #e9ecef; }
.modal-title  { font-size: 1rem; font-weight: 600; margin: 0; }
.modal-body   { padding: 18px; }
.modal-footer { padding: 12px 18px; border-top: 1px solid #e9ecef; display: flex; gap: 8px; justify-content: flex-end; }

/* ── Cash Numpad ───────────────────────────────────── */
.numpad-section { margin-bottom: 8px; }

.numpad-display {
  display: flex; align-items: center; justify-content: space-between;
  background: #f0f4ff; border-radius: 10px;
  padding: 10px 14px; margin-bottom: 10px;
}
.numpad-label  { font-size: .7rem; color: #6b7280; }
.numpad-amount { font-size: 1.7rem; font-weight: 900; color: #1e2235; }
.numpad-exact-btn {
  padding: 9px 14px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; font-size: .82rem; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: background .15s;
}
.numpad-exact-btn:hover { background: var(--accent-dark); }

.denom-row { display: flex; gap: 6px; margin-bottom: 8px; align-items: center; }
.mode-toggle-btn {
  width: 38px; height: 38px; border-radius: 8px; font-size: 1.1rem; font-weight: 800;
  border: 2px solid; cursor: pointer; transition: .15s; flex-shrink: 0; line-height: 1;
}
.mode-toggle-btn.plus-mode  { background: #dcfce7; border-color: #22c55e; color: #16a34a; }
.mode-toggle-btn.minus-mode { background: #fee2e2; border-color: #ef4444; color: #dc2626; }

.denom-btn {
  flex: 1; padding: 7px 0; border-radius: 8px;
  font-size: .88rem; font-weight: 700;
  border: 2px solid #e2e8f0; background: #f8f9fb; color: #374151;
  cursor: pointer; transition: .15s;
}
.denom-btn:hover  { border-color: var(--accent); color: var(--accent); background: #eef2ff; }
.denom-btn:active { transform: scale(.93); }

.numpad-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 6px; margin-bottom: 8px;
}
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

.numpad-change-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 4px;
}
.change-label  { font-size: .83rem; color: #6b7280; font-weight: 500; }
.change-amount { font-size: 1rem; font-weight: 800; color: #16a34a; }
.change-amount.insufficient { color: #dc2626; }

/* [REFACTOR] .np-btn 第二段（原 PosView 檔尾「數量 Numpad Modal」區塊）——
   原檔中此段覆蓋上方第一段的部分屬性，需保留先後順序以維持外觀 */
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
