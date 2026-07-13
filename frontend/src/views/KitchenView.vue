<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useToastStore }  from '@/stores/toast'
import { custOrderApi }   from '@/api/custOrder'
import AppToast from '@/components/AppToast.vue'

const toast   = useToastStore()
const orders  = ref([])
const stats   = ref({ pending: 0, processing: 0, completed: 0 })
const loading = ref(false)
const nowStr  = ref('')
const nowTs   = ref(Date.now())
let   es      = null
let   clock   = null

function tickClock() {
  nowTs.value = Date.now()
  const d = new Date(nowTs.value)
  const pad = (n) => String(n).padStart(2, '0')
  nowStr.value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 補 Z suffix：後端以 datetime.utcnow().isoformat() 存 UTC，無 suffix 時 JS 視為本地時間
function toUtcDate(isoStr) {
  if (!isoStr) return null
  return new Date(isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z')
}

const STATUS_LABEL = {
  pending:    '待處理',
  processing: '製作中',
  completed:  '已完成',
  cancelled:  '已取消',
}

// ── stats 格式統一（後端回 {count,total} 物件，取 count 作顯示數字）──
function parseStats(s) {
  const pick = (v) => (v && typeof v === 'object' ? (v.count ?? 0) : (v ?? 0))
  return {
    pending:    pick(s.pending),
    processing: pick(s.processing),
    completed:  pick(s.completed),
  }
}

// ── 初始資料載入（SSE 連上前先顯示資料）────────────────────────
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
      const s = sRes.value.data?.raw || sRes.value.data?.data || sRes.value.data || {}
      stats.value = parseStats(s)
    }
  } catch {
    toast.show('載入訂單失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── SSE 連線 ─────────────────────────────────────────────────
// [REFACTOR] 認證改為 Redis 一次性短效 ticket：
//   1. 先以 header JWT POST /customer-order/stream-ticket 取得 ticket
//   2. 再以 ?ticket= 建立 EventSource（JWT 不再進入 query string / nginx log）
// ticket 用過即失效，EventSource 內建自動重連會沿用舊 URL（舊 ticket）而 401，
// 因此改為自行管理重連：onerror 關閉舊連線 → 延遲後重新取 ticket 重建。
// 重連間隔 3 秒，與瀏覽器 EventSource 預設重連間隔一致。
const SSE_RECONNECT_MS = 3000
let sseReconnectTimer = null
let sseStopped = false

async function connectSSE() {
  if (sseStopped) return
  const token = localStorage.getItem('token')
  if (!token) return

  // [REFACTOR] 先取一次性 ticket，失敗則排程重試
  let ticket = ''
  try {
    const res = await custOrderApi.getStreamTicket()
    ticket = res.data?.ticket || ''
  } catch { /* 取 ticket 失敗（網路/未授權），走排程重試 */ }
  if (!ticket) {
    scheduleSseReconnect()
    return
  }

  es = new EventSource(`/customer-order/stream?ticket=${encodeURIComponent(ticket)}`)

  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (Array.isArray(d.orders)) orders.value = d.orders
      if (d.stats) stats.value = parseStats(d.stats)
    } catch { /* ignore parse errors */ }
  }

  es.onerror = () => {
    // [REFACTOR] ticket 為一次性，不可沿用內建自動重連；
    // 關閉舊連線後重新取 ticket 重建
    es?.close()
    es = null
    scheduleSseReconnect()
  }
}

// [REFACTOR] 自行管理的重連排程（去重：同時間僅一個 timer）
function scheduleSseReconnect() {
  if (sseStopped || sseReconnectTimer) return
  sseReconnectTimer = setTimeout(() => {
    sseReconnectTimer = null
    connectSSE()
  }, SSE_RECONNECT_MS)
}

// ── 狀態更新 ─────────────────────────────────────────────────
async function updateStatus(id, status) {
  try {
    await custOrderApi.updateStatus(id, status)
    // SSE 會在 ~2s 內自動推送最新資料，不需手動 reload
  } catch (e) {
    toast.show(e?.response?.data?.message || '更新失敗', 'danger')
  }
}

// ── v-for 穩定 key ───────────────────────────────────────────
// [OPT] 品項無 _id，改以「名稱 + 客製化序列化」組成穩定 key，
//       避免排序後以 index 為 key 造成 SSE 更新時整列重建
function itemKey(item) {
  return item._id || `${item.name || item.item_name || ''}|${JSON.stringify(item.customizations || [])}`
}
// [OPT] 客製化 c 可能是字串或物件（含 choice_id/choice_name），以內容為 key
function custKey(c) {
  return typeof c === 'object' && c !== null ? (c.choice_id || c.choice_name || JSON.stringify(c)) : c
}

// ── 時間格式 ─────────────────────────────────────────────────
function elapsedStr(createdAt) {
  if (!createdAt) return '--'
  const base = toUtcDate(createdAt)
  if (!base) return '--'
  const sec = Math.floor((nowTs.value - base.getTime()) / 1000)
  if (sec < 0) return '--'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (d > 0) return `${d}天${h}時${m}分`
  if (h > 0) return `${h}時${m}分`
  if (m > 0) return `${m}分${s}秒`
  return `${s}秒`
}

function fmtTime(createdAt) {
  if (!createdAt) return '--'
  const d = toUtcDate(createdAt)
  if (!d) return '--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// ── 生命週期 ─────────────────────────────────────────────────
onMounted(() => {
  tickClock()
  clock = setInterval(tickClock, 1000)
  loadOrders()
  connectSSE()
})
onUnmounted(() => {
  // [REFACTOR] 停止自行管理的重連迴圈，再關閉連線
  sseStopped = true
  if (sseReconnectTimer) {
    clearTimeout(sseReconnectTimer)
    sseReconnectTimer = null
  }
  es?.close()
  clearInterval(clock)
})
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

      <span class="ms-auto now-clock">{{ nowStr }}</span>

      <div class="d-flex gap-2">
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
            <span class="elapsed">{{ elapsedStr(o.created_at) }}</span>
            <span class="time-small">{{ fmtTime(o.created_at) }}</span>
          </div>
        </div>

        <!-- Items -->
        <ul class="item-list mt-2 mb-0">
          <!-- [OPT] 改用內容穩定 key（itemKey/custKey），取代排序後不穩定的 index key -->
          <li v-for="item in [...(o.items || [])].sort((a,b) => (a.name||a.item_name||'').localeCompare(b.name||b.item_name||'', 'zh-Hant'))" :key="itemKey(item)" class="item-row">
            <span class="item-qty">×{{ item.qty }}</span>
            <span class="item-name">{{ item.name || item.item_name }}</span>
            <div v-if="item.customizations?.length" class="cust-tags">
              <span v-for="c in item.customizations" :key="custKey(c)" class="cust-tag">
                {{ typeof c === 'object' ? c.choice_name : c }}
              </span>
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

.now-clock {
  font-size: .95rem; font-weight: 600; color: #ccc;
  letter-spacing: .03em; font-variant-numeric: tabular-nums;
}

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin .6s linear infinite; }
</style>
