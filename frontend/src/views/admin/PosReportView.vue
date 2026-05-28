<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate, fmtMoney } from '@/utils/format'

const toast = useToastStore()

type Period = 'day' | 'week' | 'month' | 'year'

interface ReportOrder {
  _id: string
  order_no: string
  created_at: string
  cashier: string
  total_amount: number
  payment_type: string
  status: string
}

interface Breakdown {
  period: string   // YYYY-MM-DD (week/month) or YYYY-MM (year)
  orders: number
  amount: number
  discount: number
}

interface SummaryData {
  period: Period
  date?: string
  date_from: string
  date_to: string
  total_orders: number
  total_amount: number
  total_discount: number
  cash_total: number
  card_total: number
  orders?: ReportOrder[]
  breakdown?: Breakdown[]
}

const report  = ref<SummaryData | null>(null)
const loading = ref(false)

// ── 期間選擇 ────────────────────────────────────────────
const period  = ref<Period>('day')

function todayStr()       { return new Date().toISOString().slice(0, 10) }
function currentMonth()   { return new Date().toISOString().slice(0, 7) }
function currentYear()    { return String(new Date().getFullYear()) }

const selDate  = ref(todayStr())      // day / week 共用
const selMonth = ref(currentMonth())  // month
const selYear  = ref(currentYear())   // year

// 動態計算 API 參數
const apiParams = computed(() => {
  if (period.value === 'month')  return { period: 'month', month: selMonth.value }
  if (period.value === 'year')   return { period: 'year',  year:  selYear.value }
  return { period: period.value, date: selDate.value }
})

// 標題說明
const periodLabel = computed(() => {
  switch (period.value) {
    case 'day':   return selDate.value
    case 'week':  return `${report.value?.date_from ?? ''} ～ ${report.value?.date_to ?? ''}`
    case 'month': return selMonth.value
    case 'year':  return `${selYear.value} 年`
  }
})

// 付款方式彙總（從 orders 計算）
interface PayBreak { payment_type: string; count: number; total: number }
const payBreakdown = computed<PayBreak[]>(() => {
  if (!report.value?.orders?.length) return []
  const map: Record<string, { count: number; total: number }> = {}
  for (const o of report.value.orders) {
    const k = o.payment_type || 'unknown'
    if (!map[k]) map[k] = { count: 0, total: 0 }
    map[k].count++
    map[k].total += o.total_amount || 0
  }
  return Object.entries(map).map(([payment_type, v]) => ({ payment_type, ...v }))
})

// ── 查詢 ─────────────────────────────────────────────
async function loadReport() {
  loading.value = true
  report.value  = null
  try {
    const res = await http.get('/pos/summary', { params: apiParams.value })
    report.value = res.data.data || null
  } catch {
    toast.show('載入報表失敗', 'danger')
  } finally {
    loading.value = false
  }
}

function switchPeriod(p: Period) {
  period.value = p
  loadReport()
}

// ── 年份選項（近 5 年）────────────────────────────────
const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return Array.from({ length: 5 }, (_, i) => String(y - i))
})

onMounted(loadReport)
</script>

<template>
  <div>
    <!-- 報表控制列 -->
    <div class="table-card mb-3">
      <div class="table-header">
        <h6><i class="bi bi-bar-chart-line me-1"></i>銷售報表</h6>

        <div class="toolbar flex-wrap gap-1">
          <!-- 期間切換 -->
          <div class="btn-group btn-group-sm me-1">
            <button
              v-for="p in (['day','week','month','year'] as Period[])"
              :key="p"
              class="btn"
              :class="period === p ? 'btn-primary' : 'btn-outline-secondary'"
              @click="switchPeriod(p)"
            >{{ { day:'日', week:'週', month:'月', year:'年' }[p] }}</button>
          </div>

          <!-- 日 / 週 選擇器 -->
          <template v-if="period === 'day' || period === 'week'">
            <input
              v-model="selDate"
              type="date"
              class="form-control form-control-sm"
              style="width:150px"
              @change="loadReport"
            />
          </template>

          <!-- 月 選擇器 -->
          <template v-else-if="period === 'month'">
            <input
              v-model="selMonth"
              type="month"
              class="form-control form-control-sm"
              style="width:150px"
              @change="loadReport"
            />
          </template>

          <!-- 年 選擇器 -->
          <template v-else>
            <select v-model="selYear" class="form-select form-select-sm" style="width:100px" @change="loadReport">
              <option v-for="y in yearOptions" :key="y" :value="y">{{ y }} 年</option>
            </select>
          </template>

          <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="loadReport">
            <i class="bi bi-search"></i>
          </button>
        </div>
      </div>

      <!-- 摘要卡 -->
      <div class="p-3">
        <div v-if="loading" class="text-center py-4">
          <div class="spinner-border spinner-border-sm me-2"></div>載入中…
        </div>

        <template v-else-if="report">
          <!-- 期間說明 -->
          <p class="text-muted small mb-3">
            <i class="bi bi-calendar3 me-1"></i>{{ periodLabel }}
            <span v-if="period !== 'day'" class="ms-2 text-muted">
              （{{ report.date_from }} ～ {{ report.date_to }}）
            </span>
          </p>

          <!-- 四格摘要 -->
          <div class="row g-3">
            <div class="col-6 col-lg-3">
              <div class="stat-card">
                <div class="stat-icon bg-primary bg-opacity-10 text-primary">
                  <i class="bi bi-currency-dollar"></i>
                </div>
                <div>
                  <div class="stat-num">${{ Number(report.total_amount).toLocaleString() }}</div>
                  <div class="stat-label">總銷售額</div>
                </div>
              </div>
            </div>
            <div class="col-6 col-lg-3">
              <div class="stat-card">
                <div class="stat-icon bg-success bg-opacity-10 text-success">
                  <i class="bi bi-receipt"></i>
                </div>
                <div>
                  <div class="stat-num">{{ report.total_orders }}</div>
                  <div class="stat-label">訂單數</div>
                </div>
              </div>
            </div>
            <div class="col-6 col-lg-3">
              <div class="stat-card">
                <div class="stat-icon bg-warning bg-opacity-10 text-warning">
                  <i class="bi bi-percent"></i>
                </div>
                <div>
                  <div class="stat-num">${{ Number(report.total_discount).toLocaleString() }}</div>
                  <div class="stat-label">總折扣</div>
                </div>
              </div>
            </div>
            <div class="col-6 col-lg-3">
              <div class="stat-card">
                <div class="stat-icon bg-info bg-opacity-10 text-info">
                  <i class="bi bi-cash"></i>
                </div>
                <div>
                  <div class="stat-num">${{ Number(report.cash_total).toLocaleString() }}</div>
                  <div class="stat-label">現金收入</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 付款方式明細（日模式才有 orders） -->
          <div v-if="payBreakdown.length" class="mt-4">
            <h6 class="fw-semibold mb-2">
              <i class="bi bi-credit-card me-1 text-primary"></i>付款方式明細
            </h6>
            <table class="table table-sm mb-0">
              <thead>
                <tr>
                  <th>付款方式</th>
                  <th class="text-end">筆數</th>
                  <th class="text-end">金額</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pm in payBreakdown" :key="pm.payment_type">
                  <td>{{ pm.payment_type }}</td>
                  <td class="text-end">{{ pm.count }}</td>
                  <td class="text-end fw-semibold">${{ Number(pm.total).toLocaleString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <div v-else class="text-center text-muted py-3">請選擇期間後查詢</div>
      </div>
    </div>

    <!-- 週/月：每日明細 -->
    <div v-if="report?.breakdown?.length && (period === 'week' || period === 'month')" class="table-card mb-3">
      <div class="table-header">
        <h6><i class="bi bi-calendar-week me-1"></i>
          {{ period === 'week' ? '本週每日' : '本月每日' }}銷售明細
        </h6>
      </div>
      <div class="table-responsive">
        <table class="table mb-0 table-sm">
          <thead>
            <tr>
              <th>日期</th>
              <th class="text-end">訂單數</th>
              <th class="text-end">折扣</th>
              <th class="text-end">銷售額</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in report.breakdown" :key="b.period">
              <td class="fw-semibold">{{ b.period }}</td>
              <td class="text-end">{{ b.orders }}</td>
              <td class="text-end text-muted">${{ Number(b.discount).toLocaleString() }}</td>
              <td class="text-end fw-bold text-primary">${{ Number(b.amount).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 年：每月明細 -->
    <div v-if="report?.breakdown?.length && period === 'year'" class="table-card mb-3">
      <div class="table-header">
        <h6><i class="bi bi-calendar3 me-1"></i>{{ selYear }} 年每月銷售明細</h6>
      </div>
      <div class="table-responsive">
        <table class="table mb-0 table-sm">
          <thead>
            <tr>
              <th>月份</th>
              <th class="text-end">訂單數</th>
              <th class="text-end">折扣</th>
              <th class="text-end">銷售額</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in report.breakdown" :key="b.period">
              <td class="fw-semibold">{{ b.period }}</td>
              <td class="text-end">{{ b.orders }}</td>
              <td class="text-end text-muted">${{ Number(b.discount).toLocaleString() }}</td>
              <td class="text-end fw-bold text-primary">${{ Number(b.amount).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 日：訂單明細 -->
    <div v-if="report?.orders?.length && period === 'day'" class="table-card">
      <div class="table-header">
        <h6><i class="bi bi-list-ul me-1"></i>當日訂單明細 — {{ report.date }}</h6>
      </div>
      <div class="table-responsive">
        <table class="table mb-0 table-sm">
          <thead>
            <tr>
              <th>單號</th>
              <th>時間</th>
              <th>收銀員</th>
              <th class="text-end">金額</th>
              <th>付款</th>
              <th>狀態</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in report.orders" :key="o._id">
              <td class="fw-semibold small">{{ o.order_no }}</td>
              <td class="small text-muted">{{ fmtDate(o.created_at) }}</td>
              <td class="small">{{ o.cashier || '—' }}</td>
              <td class="text-end fw-bold text-primary">
                ${{ Number(o.total_amount).toLocaleString() }}
              </td>
              <td class="small">{{ o.payment_type }}</td>
              <td>
                <span v-if="o.status === 'completed'" class="badge bg-success">已完成</span>
                <span v-else class="badge bg-secondary">{{ o.status }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
