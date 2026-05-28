<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate, fmtMoney } from '@/utils/format'

const toast = useToastStore()

// ── State ────────────────────────────────────────────────
const loading         = ref(true)
const analyticsData   = ref<any>(null)
const period          = ref<'day' | 'week' | 'month' | 'year'>('day')
const alertFilter     = ref<'all' | 'low' | 'high'>('all')
const pendingInbound  = ref(0)
const pendingOutbound = ref(0)
const productCount    = ref(0)
const warehouseCount  = ref(0)
const recentInbound   = ref<any[]>([])
const recentOutbound  = ref<any[]>([])

const periodLabels: Record<string, string> = {
  day: '今日', week: '本週', month: '本月', year: '今年',
}

// ── Computed ─────────────────────────────────────────────
const analytics = computed(() => {
  if (!analyticsData.value) return null
  return analyticsData.value[period.value]
})

const stockAlerts = computed<any[]>(() => {
  const all = analyticsData.value?.stock_alerts || []
  if (alertFilter.value === 'all') return all
  return all.filter((a: any) => a.alert === alertFilter.value || a.alert_type === alertFilter.value)
})

const alertCount = computed(() => {
  const ac = analyticsData.value?.stock_alert_count || {}
  return { low: ac.low || 0, high: ac.high || 0 }
})

const grossProfit = computed(() => {
  const a = analytics.value
  if (!a) return 0
  return a.gross_profit ?? (a.outbound?.amount - a.inbound?.amount) ?? 0
})

// ── Status badge helper ──────────────────────────────────
function statusClass(s: string) {
  const map: Record<string, string> = {
    pending: 'badge-pending', confirmed: 'badge-confirmed',
    completed: 'badge-completed', cancelled: 'badge-cancelled',
  }
  return map[s] || 'bg-secondary'
}
function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待處理', confirmed: '已確認',
    completed: '已完成', cancelled: '已取消',
  }
  return map[s] || s
}

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [prodR, whR, ibPendR, obPendR, ibRecentR, obRecentR, analR] = await Promise.all([
      http.get('/product/').catch(() => ({ data: { data: [] } })),
      http.get('/warehouse/').catch(() => ({ data: { data: [] } })),
      http.get('/inbound/?status=pending').catch(() => ({ data: { data: [] } })),
      http.get('/outbound/?status=pending').catch(() => ({ data: { data: [] } })),
      http.get('/inbound/').catch(() => ({ data: { data: [] } })),
      http.get('/outbound/').catch(() => ({ data: { data: [] } })),
      http.get('/analytics/summary').catch(() => null),
    ])

    productCount.value    = (prodR.data?.data || []).length
    warehouseCount.value  = (whR.data?.data   || []).length
    pendingInbound.value  = (ibPendR.data?.data || []).length
    pendingOutbound.value = (obPendR.data?.data || []).length
    recentInbound.value   = (ibRecentR.data?.data || []).slice(0, 5)
    recentOutbound.value  = (obRecentR.data?.data || []).slice(0, 5)

    if (analR?.data?.data) analyticsData.value = analR.data.data
  } catch (e: any) {
    toast.show('儀表板載入失敗：' + (e?.message || e), 'danger')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- ── Stat Cards ─────────────────────────────────────── -->
  <div class="row g-3 mb-4">
    <div class="col-6 col-lg-3">
      <div class="stat-card">
        <div class="stat-icon bg-primary bg-opacity-10 text-primary"><i class="bi bi-box-seam"></i></div>
        <div>
          <div class="stat-num">{{ loading ? '-' : productCount }}</div>
          <div class="stat-label">產品總數</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card">
        <div class="stat-icon bg-success bg-opacity-10 text-success"><i class="bi bi-building"></i></div>
        <div>
          <div class="stat-num">{{ loading ? '-' : warehouseCount }}</div>
          <div class="stat-label">倉庫數量</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card">
        <div class="stat-icon bg-warning bg-opacity-10 text-warning"><i class="bi bi-box-arrow-in-down"></i></div>
        <div>
          <div class="stat-num">{{ loading ? '-' : pendingInbound }}</div>
          <div class="stat-label">待處理入庫</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card">
        <div class="stat-icon bg-danger bg-opacity-10 text-danger"><i class="bi bi-box-arrow-up"></i></div>
        <div>
          <div class="stat-num">{{ loading ? '-' : pendingOutbound }}</div>
          <div class="stat-label">待處理出庫</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Analytics ──────────────────────────────────────── -->
  <div class="table-card mb-3">
    <div class="table-header">
      <h6><i class="bi bi-bar-chart-line me-1 text-primary"></i>分析用量</h6>
      <ul class="nav nav-pills nav-sm" id="analytics-tabs">
        <li v-for="(label, key) in periodLabels" :key="key" class="nav-item">
          <a
            class="nav-link"
            :class="{ active: period === key }"
            href="#"
            @click.prevent="period = key as any"
          >{{ label }}</a>
        </li>
      </ul>
    </div>
    <div class="p-3">
      <div v-if="loading" class="text-center text-muted py-3">
        <div class="spinner-border spinner-border-sm me-2"></div>載入中…
      </div>
      <div v-else-if="analytics" class="row g-3">
        <!-- 入庫 -->
        <div class="col-12">
          <p class="text-muted small mb-1 fw-semibold">
            <i class="bi bi-box-arrow-in-down me-1"></i>入庫
          </p>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-warning bg-opacity-10 text-warning"><i class="bi bi-file-earmark-text"></i></div>
            <div>
              <div class="stat-num">{{ analytics.inbound?.orders ?? 0 }}</div>
              <div class="stat-label">{{ periodLabels[period] }}入庫單（新建）</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-success bg-opacity-10 text-success"><i class="bi bi-check2-circle"></i></div>
            <div>
              <div class="stat-num">{{ analytics.inbound?.completed ?? 0 }}</div>
              <div class="stat-label">{{ periodLabels[period] }}入庫完成</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-warning bg-opacity-10 text-warning"><i class="bi bi-archive"></i></div>
            <div>
              <div class="stat-num">{{ (analytics.inbound?.qty ?? 0).toLocaleString() }}</div>
              <div class="stat-label">{{ periodLabels[period] }}實際入庫件數</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-warning bg-opacity-10 text-warning"><i class="bi bi-currency-dollar"></i></div>
            <div>
              <div class="stat-num">{{ fmtMoney(analytics.inbound?.amount ?? 0, '$') }}</div>
              <div class="stat-label">{{ periodLabels[period] }}進貨金額</div>
            </div>
          </div>
        </div>

        <!-- 出庫 -->
        <div class="col-12">
          <p class="text-muted small mb-1 fw-semibold">
            <i class="bi bi-box-arrow-up me-1"></i>出庫
          </p>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-danger bg-opacity-10 text-danger"><i class="bi bi-file-earmark-text"></i></div>
            <div>
              <div class="stat-num">{{ analytics.outbound?.orders ?? 0 }}</div>
              <div class="stat-label">{{ periodLabels[period] }}出庫單（新建）</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-info bg-opacity-10 text-info"><i class="bi bi-check2-circle"></i></div>
            <div>
              <div class="stat-num">{{ analytics.outbound?.completed ?? 0 }}</div>
              <div class="stat-label">{{ periodLabels[period] }}出庫完成</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-danger bg-opacity-10 text-danger"><i class="bi bi-send"></i></div>
            <div>
              <div class="stat-num">{{ (analytics.outbound?.qty ?? 0).toLocaleString() }}</div>
              <div class="stat-label">{{ periodLabels[period] }}實際出庫件數</div>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon bg-danger bg-opacity-10 text-danger"><i class="bi bi-currency-dollar"></i></div>
            <div>
              <div class="stat-num">{{ fmtMoney(analytics.outbound?.amount ?? 0, '$') }}</div>
              <div class="stat-label">{{ periodLabels[period] }}出貨金額</div>
            </div>
          </div>
        </div>

        <!-- 毛利 -->
        <div class="col-12">
          <div
            class="stat-card border-start border-4"
            :class="grossProfit >= 0 ? 'border-success' : 'border-danger'"
          >
            <div
              class="stat-icon bg-opacity-10"
              :class="grossProfit >= 0 ? 'bg-success text-success' : 'bg-danger text-danger'"
            >
              <i class="bi" :class="grossProfit >= 0 ? 'bi-graph-up-arrow' : 'bi-graph-down-arrow'"></i>
            </div>
            <div class="flex-grow-1">
              <div class="d-flex align-items-baseline gap-3">
                <div
                  class="stat-num"
                  :class="grossProfit >= 0 ? 'text-success' : 'text-danger'"
                >{{ fmtMoney(grossProfit, '$') }}</div>
                <span
                  v-if="analytics.outbound?.amount > 0"
                  class="badge bg-opacity-75 fs-6"
                  :class="grossProfit >= 0 ? 'bg-success' : 'bg-danger'"
                >
                  {{ (grossProfit / analytics.outbound.amount * 100).toFixed(1) }}%
                </span>
              </div>
              <div class="stat-label">{{ periodLabels[period] }}毛利（出貨 − 進貨）</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-center text-muted py-3">無分析資料</div>
    </div>
  </div>

  <!-- ── Stock Alerts ───────────────────────────────────── -->
  <div class="table-card mb-3">
    <div class="table-header">
      <h6>
        <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>庫存警示
        <span v-if="alertCount.low + alertCount.high > 0">
          <span class="badge bg-danger ms-1">{{ alertCount.low }} 低庫存</span>
          <span class="badge bg-primary ms-1">{{ alertCount.high }} 超量</span>
        </span>
        <span v-else-if="!loading" class="badge bg-success ms-1">無異常</span>
      </h6>
      <div class="btn-group btn-group-sm">
        <button
          v-for="[key, label] in [['all','全部'],['low','低庫存'],['high','超量']]"
          :key="key"
          class="btn"
          :class="alertFilter === key
            ? (key==='low' ? 'btn-danger' : key==='high' ? 'btn-primary' : 'btn-secondary')
            : 'btn-outline-secondary'"
          @click="alertFilter = key as any"
        >{{ label }}</button>
      </div>
    </div>
    <div class="table-responsive">
      <table class="table mb-0 table-sm">
        <thead>
          <tr>
            <th>SKU</th><th>產品名稱</th><th>倉庫</th>
            <th class="text-end">現有庫存</th>
            <th class="text-end">最低</th><th class="text-end">最高</th>
            <th>狀態</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!stockAlerts.length">
            <td colspan="7" class="text-center text-muted py-3">
              {{ (alertCount.low + alertCount.high) === 0 ? '目前無庫存異常' : '此分類無異常' }}
            </td>
          </tr>
          <tr v-for="a in stockAlerts" :key="`${a.product_id}_${a.warehouse_id}`">
            <td class="text-muted small">{{ a.product_sku }}</td>
            <td>{{ a.product_name }}</td>
            <td class="text-muted small">{{ a.warehouse_name }}</td>
            <td
              class="text-end fw-bold"
              :class="(a.alert || a.alert_type) === 'low' ? 'text-danger' : 'text-primary'"
            >{{ a.quantity }}</td>
            <td class="text-end text-muted small">{{ a.min_stock > 0 ? a.min_stock : '-' }}</td>
            <td class="text-end text-muted small">{{ a.max_stock > 0 ? a.max_stock : '-' }}</td>
            <td>
              <span
                class="badge"
                :class="(a.alert || a.alert_type) === 'low' ? 'bg-danger' : 'bg-primary'"
              >
                {{ (a.alert || a.alert_type) === 'low' ? '低庫存' : '超量' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Recent Orders ──────────────────────────────────── -->
  <div class="row g-3">
    <div class="col-12 col-lg-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-clock-history me-1 text-warning"></i>最新入庫單</h6>
        </div>
        <div class="table-responsive">
          <table class="table mb-0">
            <thead><tr><th>單號</th><th>倉庫</th><th>狀態</th><th>日期</th></tr></thead>
            <tbody>
              <tr v-if="!recentInbound.length">
                <td colspan="4" class="text-center text-muted py-2">無資料</td>
              </tr>
              <tr v-for="r in recentInbound" :key="r._id">
                <td class="fw-semibold small">{{ r.order_no }}</td>
                <td class="small">{{ r.warehouse_name || '-' }}</td>
                <td>
                  <span class="order-status" :class="statusClass(r.status)">
                    {{ statusLabel(r.status) }}
                  </span>
                </td>
                <td class="text-muted small">{{ fmtDate(r.created_at)?.slice(0, 10) || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="col-12 col-lg-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-clock-history me-1 text-danger"></i>最新出庫單</h6>
        </div>
        <div class="table-responsive">
          <table class="table mb-0">
            <thead><tr><th>單號</th><th>倉庫</th><th>狀態</th><th>日期</th></tr></thead>
            <tbody>
              <tr v-if="!recentOutbound.length">
                <td colspan="4" class="text-center text-muted py-2">無資料</td>
              </tr>
              <tr v-for="r in recentOutbound" :key="r._id">
                <td class="fw-semibold small">{{ r.order_no }}</td>
                <td class="small">{{ r.warehouse_name || '-' }}</td>
                <td>
                  <span class="order-status" :class="statusClass(r.status)">
                    {{ statusLabel(r.status) }}
                  </span>
                </td>
                <td class="text-muted small">{{ fmtDate(r.created_at)?.slice(0, 10) || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
#analytics-tabs .nav-link { padding: 3px 12px; font-size: .82rem; }
#analytics-tabs .nav-link.active { background: var(--accent); color: #fff; }
</style>
