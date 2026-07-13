<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- ── 今日銷售記錄 Modal ─────────────────────── -->
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop-custom" @click.self="close()">
      <div class="modal-box-history">

        <!-- Header -->
        <div class="modal-header">
          <div>
            <h5 class="modal-title">
              <i class="bi bi-clock-history me-2"></i>今日銷售記錄
            </h5>
            <div class="text-muted small mt-1">{{ todayStr }} · 共 {{ historyOrders.length }} 筆</div>
          </div>
          <button class="btn-close" @click="close()"></button>
        </div>

        <!-- Body -->
        <div class="hist-body">
          <div v-if="historyLoading" class="text-center py-5">
            <div class="spinner-border text-primary"></div>
            <div class="text-muted small mt-2">載入中…</div>
          </div>
          <div v-else-if="!historyOrders.length" class="text-center py-5 text-muted">
            <i class="bi bi-inbox" style="font-size:2.2rem"></i>
            <div class="mt-2">今日尚無銷售記錄</div>
          </div>
          <div v-else>
            <div v-for="o in historyOrders" :key="o._id">

              <!-- 摘要行（可點擊展開） -->
              <div class="hist-row"
                   :class="{ refunded: o.status === 'refunded', 'hist-row-expanded': expandedOrderId === o._id }"
                   @click="toggleOrderDetail(o._id)">

                <!-- 時間 -->
                <div class="hist-time">{{ fmtTime(o.created_at) }}</div>

                <!-- 訂單資訊 -->
                <div class="hist-info">
                  <div class="hist-no">#{{ o.order_no }}</div>
                  <div class="hist-items">
                    <template v-if="o.items?.length">
                      {{ o.items.slice(0,4).map((i:any) => i.product_name).join('、') }}
                      <span v-if="o.items.length > 4" class="text-muted">…等 {{ o.items.length }} 項</span>
                    </template>
                    <template v-else-if="o.items_count">{{ o.items_count }} 項商品</template>
                  </div>
                  <div class="hist-meta-row">
                    <span class="hist-cashier"><i class="bi bi-person me-1"></i>{{ o.cashier }}</span>
                    <span v-if="o.remark" class="hist-remark"
                          ><i class="bi bi-chat-left-text me-1"></i>{{ o.remark }}</span>
                  </div>
                </div>

                <!-- 付款方式 + 狀態 -->
                <div class="hist-tags">
                  <span class="hist-pay-badge">{{ PAY_LABEL[o.payment_type] || o.payment_type }}</span>
                  <span :class="`badge ${o.status === 'refunded' ? 'bg-danger' : 'bg-success'}`">
                    {{ o.status === 'refunded' ? '已退款' : '完成' }}
                  </span>
                </div>

                <!-- 金額 -->
                <div class="hist-amount">
                  <div class="hist-total"
                       :class="{ 'text-decoration-line-through text-muted': o.status === 'refunded' }">
                    NT$&nbsp;{{ o.total_amount?.toLocaleString() }}
                  </div>
                  <div v-if="o.discount > 0" class="hist-discount">折 -{{ o.discount }}</div>
                </div>

                <!-- 展開箭頭 -->
                <div class="hist-chevron">
                  <i class="bi" :class="expandedOrderId === o._id ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                </div>

              </div>

              <!-- 展開的品項明細 -->
              <div v-if="expandedOrderId === o._id" class="hist-detail-panel">
                <div v-if="!o.items?.length" class="hist-detail-empty">無品項資料</div>
                <div v-for="(item, idx) in o.items" :key="idx" class="hist-detail-item">
                  <div class="hdi-left">
                    <span class="hdi-name">{{ item.product_name }}</span>
                    <span v-if="item.customizations_selected?.length" class="hdi-custom">
                      {{ item.customizations_selected.map((c:any) => c.choice_name).join(' · ') }}
                    </span>
                  </div>
                  <div class="hdi-right">
                    <span class="hdi-qty">× {{ item.quantity }}</span>
                    <span class="hdi-price">NT$&nbsp;{{ (item.unit_price * item.quantity).toLocaleString() }}</span>
                  </div>
                </div>
                <div v-if="o.discount > 0" class="hist-detail-discount">
                  <span>折扣</span>
                  <span class="text-danger fw-bold">- NT$ {{ o.discount }}</span>
                </div>
              </div>

            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="modal-footer">
          <div class="hist-summary" v-if="historyOrders.length">
            今日實收合計：
            <strong class="text-primary" style="font-size:1.1rem">
              NT$&nbsp;{{ historyTotal.toLocaleString() }}
            </strong>
            <span class="text-muted small ms-2">（不含退款）</span>
          </div>
          <button class="btn btn-primary px-4" @click="loadHistory">
            <i class="bi bi-arrow-clockwise me-1"></i>重新整理
          </button>
          <button class="btn btn-secondary px-4" @click="close()">關閉</button>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
}>()

const toast = useToastStore()

const historyOrders   = ref<any[]>([])
const historyLoading  = ref(false)
const expandedOrderId = ref<string | null>(null)

function toggleOrderDetail(id: string) {
  expandedOrderId.value = expandedOrderId.value === id ? null : id
}

function close() { emit('update:show', false) }

// ── 今日銷售記錄 ──────────────────────────────────
const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`
})

const historyTotal = computed(() =>
  historyOrders.value
    .filter(o => o.status !== 'refunded')
    .reduce((s, o) => s + (o.total_amount || 0), 0)
)

function fmtTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.includes('Z') || iso.includes('+') ? iso : iso + 'Z')
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const PAY_LABEL: Record<string, string> = {
  cash: '現金', card: '刷卡', mixed: '混合', linepay: 'LINE Pay', zpay: '全支付',
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const today = new Date().toLocaleDateString('sv')   // YYYY-MM-DD
    const res = await http.get('/pos/sales', {
      params: { date_from: today, date_to: today, limit: 500 },
    })
    const list: any[] = res.data.data || []
    // 確保最新在前
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    historyOrders.value = list
  } catch {
    toast.show('載入銷售記錄失敗', 'danger')
  } finally {
    historyLoading.value = false
  }
}

watch(() => props.show, val => {
  if (val) { expandedOrderId.value = null; loadHistory() }
})
</script>

<style scoped>
/* Modal backdrop（複製自 PosView.vue 共用樣式） */
.modal-backdrop-custom { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1050; display: flex; align-items: center; justify-content: center; overflow-y: auto; padding: 16px; }

.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #e9ecef; }
.modal-title  { font-size: 1rem; font-weight: 600; margin: 0; }
.modal-body   { padding: 18px; }
.modal-footer { padding: 12px 18px; border-top: 1px solid #e9ecef; display: flex; gap: 8px; justify-content: flex-end; }

/* ── 銷售記錄 Modal ──────────────────────────────── */
.modal-box-history {
  background: #fff;
  border-radius: 14px;
  width: 900px;
  max-width: 96vw;
  height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,.35);
}
.hist-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
.hist-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid #f3f4f6;
  transition: background .1s;
}
.hist-row:hover { background: #f8f9ff; }
.hist-row.refunded { opacity: .65; }
.hist-time {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--accent);
  min-width: 56px;
  font-variant-numeric: tabular-nums;
  letter-spacing: .5px;
}
.hist-info {
  flex: 1;
  min-width: 0;
}
.hist-no {
  font-weight: 700;
  font-size: .88rem;
  color: #1e2235;
}
.hist-items {
  font-size: .78rem;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
.hist-meta-row {
  display: flex;
  gap: 12px;
  margin-top: 3px;
}
.hist-cashier {
  font-size: .72rem;
  color: #9ca3af;
}
.hist-remark {
  font-size: .72rem;
  color: #9ca3af;
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hist-tags {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 72px;
}
.hist-pay-badge {
  font-size: .72rem;
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 20px;
  font-weight: 600;
  white-space: nowrap;
}
.hist-amount {
  text-align: right;
  min-width: 96px;
}
.hist-total {
  font-size: 1.05rem;
  font-weight: 800;
  color: #1e2235;
}
.hist-discount {
  font-size: .72rem;
  color: #ef4444;
  margin-top: 2px;
}
.hist-summary {
  flex: 1;
  font-size: .9rem;
  color: #374151;
}

/* 展開箭頭 */
.hist-row { cursor: pointer; }
.hist-chevron {
  color: #9ca3af;
  font-size: .85rem;
  flex-shrink: 0;
  width: 18px;
  text-align: center;
  transition: color .15s;
}
.hist-row:hover .hist-chevron { color: var(--accent); }
.hist-row-expanded { background: #f0f4ff !important; }

/* 品項明細展開面板 */
.hist-detail-panel {
  background: #f8faff;
  border-bottom: 2px solid #c7d2fe;
  padding: 10px 20px 12px 92px;
}
.hist-detail-empty {
  font-size: .78rem;
  color: #9ca3af;
  font-style: italic;
}
.hist-detail-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px dashed #e0e7ff;
  gap: 12px;
}
.hist-detail-item:last-child { border-bottom: none; }
.hdi-left { flex: 1; min-width: 0; }
.hdi-name {
  font-size: .85rem;
  font-weight: 600;
  color: #1e2235;
}
.hdi-custom {
  display: block;
  font-size: .72rem;
  color: #6366f1;
  margin-top: 1px;
}
.hdi-right {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-shrink: 0;
}
.hdi-qty {
  font-size: .78rem;
  color: #6b7280;
  min-width: 32px;
  text-align: right;
}
.hdi-price {
  font-size: .88rem;
  font-weight: 700;
  color: var(--accent);
  min-width: 84px;
  text-align: right;
}
.hist-detail-discount {
  display: flex;
  justify-content: space-between;
  padding: 6px 0 2px;
  font-size: .78rem;
  color: #6b7280;
  border-top: 1px solid #e0e7ff;
  margin-top: 4px;
}
</style>
