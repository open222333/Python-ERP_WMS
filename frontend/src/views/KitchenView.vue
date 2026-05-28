<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useToastStore }  from '@/stores/toast'
import { custOrderApi }   from '@/api/custOrder'
import AppToast from '@/components/AppToast.vue'

const toast   = useToastStore()
const orders  = ref([])
const stats   = ref({ pending: 0, processing: 0, completed: 0 })
const loading = ref(false)
let   timer   = null

const STATUS_LABEL = {
  pending:    '待處理',
  processing: '製作中',
  completed:  '已完成',
  cancelled:  '已取消',
}

// ── 資料載入 ─────────────────────────────────────────────────
async function loadOrders() {
  loading.value = true
  try {
    const [oRes, sRes] = await Promise.allSettled([
      custOrderApi.getActive(),
      custOrderApi.getStats(),
    ])
    if (oRes.status === 'fulfilled') {
      orders.value = oRes.value.data?.data || oRes.value.data || []
    }
    if (sRes.status === 'fulfilled') {
      stats.value = sRes.value.data?.data || sRes.value.data || stats.value
    }
  } catch (e) {
    toast.show('載入訂單失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── 狀態更新 ─────────────────────────────────────────────────
async function updateStatus(id, status) {
  try {
    await custOrderApi.updateStatus(id, status)
    await loadOrders()
  } catch (e) {
    toast.show(e?.response?.data?.message || '更新失敗', 'danger')
  }
}

// ── 時間格式 ─────────────────────────────────────────────────
function elapsedMin(createdAt) {
  if (!createdAt) return 0
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 60000)
}

function fmtTime(createdAt) {
  if (!createdAt) return '--:--'
  const d = new Date(createdAt)
  return d.toTimeString().slice(0, 5)
}

// ── 生命週期 ─────────────────────────────────────────────────
onMounted(() => {
  loadOrders()
  timer = setInterval(loadOrders, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="kitchen-wrap" style="min-height:100vh;background:#111;color:#eee">
    <!-- ── Topbar ──────────────────────────────────────────── -->
    <header class="kitchen-topbar d-flex align-items-center gap-3 px-3">
      <i class="bi bi-grid-3x3-gap-fill text-success fs-5"></i>
      <span class="fw-bold fs-5">備餐顯示</span>

      <!-- 統計 -->
      <div class="stat-chips ms-2">
        <span class="stat-chip chip-pending">待處理 {{ stats.pending }}</span>
        <span class="stat-chip chip-process">製作中 {{ stats.processing }}</span>
        <span class="stat-chip chip-done">已完成 {{ stats.completed }}</span>
      </div>

      <div class="ms-auto d-flex gap-2">
        <button class="btn btn-sm btn-outline-light" :class="{ disabled: loading }" @click="loadOrders">
          <i class="bi bi-arrow-clockwise" :class="{ 'spin': loading }"></i>
        </button>
        <a href="/admin/cust-orders" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-grid-1x2"></i>
        </a>
      </div>
    </header>

    <!-- ── Order Cards ─────────────────────────────────────── -->
    <div class="orders-grid p-3">
      <div v-if="!orders.length && !loading"
           class="no-orders text-center text-muted py-5">
        <i class="bi bi-check2-circle fs-1 d-block mb-2 text-success"></i>
        目前無待處理訂單
      </div>

      <div v-for="o in orders" :key="o._id"
           class="order-card"
           :class="`status-${o.status}`">
        <!-- Card header -->
        <div class="order-head d-flex align-items-center justify-content-between">
          <div>
            <span class="order-no">#{{ o.order_no || o._id?.slice(-4) }}</span>
            <span v-if="o.table_no" class="table-badge ms-2">桌 {{ o.table_no }}</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="elapsed" :class="elapsedMin(o.created_at) >= 10 ? 'elapsed-warn' : ''">
              {{ elapsedMin(o.created_at) }}分
            </span>
            <span class="time-small">{{ fmtTime(o.created_at) }}</span>
          </div>
        </div>

        <!-- Items -->
        <ul class="item-list mt-2 mb-0">
          <li v-for="(item, i) in (o.items || [])" :key="i" class="item-row">
            <span class="item-qty">×{{ item.qty }}</span>
            <span class="item-name">{{ item.name || item.item_name }}</span>
            <div v-if="item.customizations?.length" class="cust-tags">
              <span v-for="c in item.customizations" :key="c" class="cust-tag">{{ c }}</span>
            </div>
          </li>
        </ul>

        <!-- Remark -->
        <div v-if="o.remark" class="remark mt-2">
          <i class="bi bi-chat-left-text-fill me-1"></i>{{ o.remark }}
        </div>

        <!-- Actions -->
        <div class="card-actions mt-3 d-flex gap-2">
          <button v-if="o.status === 'pending'"
                  class="btn btn-sm btn-warning flex-grow-1 fw-semibold"
                  @click="updateStatus(o._id, 'processing')">
            <i class="bi bi-fire me-1"></i>開始製作
          </button>
          <button v-if="o.status === 'processing'"
                  class="btn btn-sm btn-success flex-grow-1 fw-semibold"
                  @click="updateStatus(o._id, 'completed')">
            <i class="bi bi-check-lg me-1"></i>完成出餐
          </button>
          <button v-if="['pending','processing'].includes(o.status)"
                  class="btn btn-sm btn-outline-danger"
                  @click="updateStatus(o._id, 'cancelled')">
            取消
          </button>
        </div>
      </div>
    </div>

    <AppToast />
  </div>
</template>

<style scoped>
.kitchen-topbar {
  height: 54px;
  background: #1a1a2e;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.stat-chips { display: flex; gap: 8px; }
.stat-chip {
  padding: 3px 10px; border-radius: 20px; font-size: .8rem; font-weight: 600;
}
.chip-pending { background: #5c5c00; color: #ffd700; }
.chip-process { background: #004d60; color: #00e5ff; }
.chip-done    { background: #004d1a; color: #00e676; }

.orders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  align-content: start;
}

.order-card {
  background: #1e1e2e;
  border: 2px solid #333;
  border-radius: 12px;
  padding: 14px;
  transition: border-color .2s;
}
.order-card.status-pending    { border-color: #b8860b; }
.order-card.status-processing { border-color: #0288d1; }
.order-card.status-completed  { opacity: .55; border-color: #2e7d32; }

.order-no   { font-size: 1.1rem; font-weight: 700; color: #fff; }
.table-badge {
  background: #4a4a6a; color: #ccc;
  border-radius: 6px; padding: 1px 7px; font-size: .78rem;
}
.elapsed      { font-size: .8rem; color: #aaa; }
.elapsed-warn { color: #ff6b6b; font-weight: 700; }
.time-small   { font-size: .75rem; color: #666; }

.item-list { list-style: none; padding: 0; margin: 0; }
.item-row  { display: flex; align-items: flex-start; gap: 8px; padding: 4px 0; font-size: .9rem; }
.item-qty  { color: #0dcaf0; font-weight: 700; flex-shrink: 0; min-width: 28px; }
.item-name { color: #ddd; flex: 1; }

.cust-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 3px; }
.cust-tag  {
  background: #333; color: #aaa;
  border-radius: 4px; padding: 1px 6px; font-size: .7rem;
}

.remark {
  font-size: .78rem; color: #ffb74d;
  background: rgba(255,183,77,.08);
  border-left: 3px solid #ffb74d;
  padding: 4px 8px; border-radius: 0 4px 4px 0;
}

.no-orders { width: 100%; }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin .6s linear infinite; }
</style>
