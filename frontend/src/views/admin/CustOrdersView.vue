<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate, ORDER_STATUS_COLOR, ORDER_STATUS_LABEL } from '@/utils/format'

const toast = useToastStore()

interface CustOrderItem {
  item_id: string
  item_name: string
  qty: number
  price: number
  customizations?: string[]
  note?: string
}

interface CustOrder {
  _id: string
  order_no: string
  table_no: string
  items: CustOrderItem[]
  total_amount: number
  status: string
  remark?: string
  created_at: string
}

interface Stats {
  pending?: { count: number; total: number }
  processing?: { count: number; total: number }
  completed?: { count: number; total: number }
  cancelled?: { count: number; total: number }
}

const orders = ref<CustOrder[]>([])
const stats = ref<Stats>({})
const loading = ref(false)
const statusFilter = ref('')
const dateFilter = ref('')
let refreshTimer: ReturnType<typeof setInterval> | null = null

const statusOptions = [
  { value: '', label: '全部狀態' },
  { value: 'pending', label: '待處理' },
  { value: 'processing', label: '處理中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

async function loadOrders() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (dateFilter.value) params.date = dateFilter.value
    const [ordRes, statRes] = await Promise.all([
      http.get('/customer-order/', { params }),
      http.get('/customer-order/stats'),
    ])
    orders.value = ordRes.data.data || []
    stats.value = statRes.data.raw || {}
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function updateStatus(id: string, status: string) {
  try {
    await http.put(`/api/customer-order/${id}/status`, { status })
    toast.show('狀態已更新', 'success')
    await loadOrders()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '更新失敗', 'danger')
  }
}

function getStatusColor(status: string): string {
  return ORDER_STATUS_COLOR[status] || 'secondary'
}

function getStatusLabel(status: string): string {
  return ORDER_STATUS_LABEL[status] || status
}

function formatItems(items: CustOrderItem[]): string {
  if (!items?.length) return '—'
  return items.map(i => `${i.item_name} ×${i.qty}`).join('、')
}

onMounted(() => {
  loadOrders()
  refreshTimer = setInterval(loadOrders, 10000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div>
    <div class="table-card">
      <div class="table-header d-flex align-items-center justify-content-between flex-wrap gap-2">
        <h6><i class="bi bi-receipt me-1 text-primary"></i>訂單管理</h6>
        <div class="d-flex gap-2 flex-wrap">
          <select
            v-model="statusFilter"
            class="form-select form-select-sm"
            style="width:auto"
            @change="loadOrders"
          >
            <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
          <input
            v-model="dateFilter"
            type="date"
            class="form-control form-control-sm"
            style="width:auto"
            @change="loadOrders"
          />
          <button class="btn btn-sm btn-outline-secondary" @click="loadOrders">
            <i class="bi bi-arrow-clockwise"></i>
          </button>
          <a href="/kitchen/" target="_blank" class="btn btn-sm btn-outline-primary">
            <i class="bi bi-grid-3x3-gap me-1"></i>備餐顯示
          </a>
        </div>
      </div>

      <!-- 今日統計 -->
      <div class="d-flex gap-3 px-3 py-2 border-bottom flex-wrap">
        <span class="small">
          <span class="text-warning fw-semibold">待處理：</span>
          <span class="fw-bold">{{ stats.pending?.count ?? 0 }}</span>
        </span>
        <span class="small">
          <span class="text-primary fw-semibold">處理中：</span>
          <span class="fw-bold">{{ stats.processing?.count ?? 0 }}</span>
        </span>
        <span class="small">
          <span class="text-success fw-semibold">今日完成：</span>
          <span class="fw-bold">{{ stats.completed?.count ?? 0 }}</span>
        </span>
        <span v-if="stats.completed?.total" class="small text-muted">
          · 完成金額：${{ Number(stats.completed.total).toLocaleString() }}
        </span>
      </div>

      <div class="table-responsive">
        <table class="table mb-0">
          <thead>
            <tr>
              <th>訂單編號</th>
              <th>桌號/姓名</th>
              <th>品項</th>
              <th class="text-end">金額</th>
              <th>狀態</th>
              <th>時間</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="text-center py-3">
                <div class="spinner-border spinner-border-sm me-2"></div>載入中…
              </td>
            </tr>
            <tr v-else-if="!orders.length">
              <td colspan="7" class="text-center text-muted py-3">無訂單資料</td>
            </tr>
            <tr v-for="o in orders" :key="o._id">
              <td class="fw-semibold small">{{ o.order_no || o._id.slice(-8) }}</td>
              <td>{{ o.table_no || '—' }}</td>
              <td class="small text-muted">{{ formatItems(o.items) }}</td>
              <td class="text-end fw-semibold">${{ Number(o.total_amount || 0).toLocaleString() }}</td>
              <td>
                <span :class="`badge bg-${getStatusColor(o.status)}`">
                  {{ getStatusLabel(o.status) }}
                </span>
              </td>
              <td class="small text-muted">{{ fmtDate(o.created_at) }}</td>
              <td>
                <div class="d-flex gap-1 flex-wrap">
                  <button
                    v-if="o.status === 'pending'"
                    class="btn btn-xs btn-outline-primary"
                    @click="updateStatus(o._id, 'processing')"
                  >
                    <i class="bi bi-play-fill"></i> 處理
                  </button>
                  <button
                    v-if="o.status === 'processing'"
                    class="btn btn-xs btn-success"
                    @click="updateStatus(o._id, 'completed')"
                  >
                    <i class="bi bi-check-lg"></i> 完成
                  </button>
                  <button
                    v-if="['pending', 'processing'].includes(o.status)"
                    class="btn btn-xs btn-outline-danger"
                    @click="updateStatus(o._id, 'cancelled')"
                  >
                    取消
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn-xs {
  padding: .15rem .4rem;
  font-size: .75rem;
}
</style>
