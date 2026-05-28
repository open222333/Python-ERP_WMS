<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'

const toast = useToastStore()

const exporting  = ref(false)
const importing  = ref(false)
const fileInput  = ref<HTMLInputElement>()

// ── 匯出 CSV ──────────────────────────────────────────
async function exportCsv() {
  exporting.value = true
  try {
    const params = new URLSearchParams()
    if (dateFrom.value)      params.set('date_from', dateFrom.value)
    if (dateTo.value)        params.set('date_to',   dateTo.value)
    if (cashierFilter.value) params.set('cashier',   cashierFilter.value)
    if (statusFilter.value)  params.set('status',    statusFilter.value)
    if (sourceFilter.value)  params.set('source',    sourceFilter.value)

    const token = localStorage.getItem('token')
    const res = await fetch(`/pos/sales/export?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('匯出失敗')
    const blob = await res.blob()
    const cd   = res.headers.get('Content-Disposition') || ''
    const match = cd.match(/filename="?([^"]+)"?/)
    const name  = match ? match[1] : `pos_sales_${new Date().toISOString().slice(0, 10)}.csv`
    const url = URL.createObjectURL(blob)
    const a   = document.createElement('a')
    a.href = url; a.download = name; a.click()
    URL.revokeObjectURL(url)
    toast.show('已匯出銷售記錄', 'success')
  } catch (e: any) {
    toast.show(e?.message || '匯出失敗', 'danger')
  } finally {
    exporting.value = false
  }
}

// ── 匯入 CSV / JSON ────────────────────────────────────
function openImport() { fileInput.value?.click() }

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await http.post('/pos/sales/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    toast.show(`匯入完成：共 ${data.inserted} 筆`, 'success')
    await loadSales()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '匯入失敗', 'danger')
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

interface PosItem {
  product_name: string
  product_sku: string
  quantity: number
  unit_price: number
  subtotal: number
}

interface PosSaleRecord {
  _id: string
  order_no: string
  source?: string
  warehouse_name?: string
  cashier?: string
  items: PosItem[]
  subtotal: number
  discount: number
  total_amount: number
  payment_type: string
  cash_amount?: number
  change_amount?: number
  status: string
  remark?: string
  created_at: string
}

const sales = ref<PosSaleRecord[]>([])
const loading = ref(false)
const dateFrom = ref('')
const dateTo = ref('')
const cashierFilter = ref('')
const statusFilter = ref('')
const sourceFilter = ref('')

const selectedSale = ref<PosSaleRecord | null>(null)
const showModal = ref(false)
const refundReason = ref('')
const refunding = ref(false)

const SOURCE_LABEL: Record<string, string> = {
  pos: 'POS 現場',
  ubereats: 'UberEats',
  foodpanda: 'foodpanda',
}
const SOURCE_COLOR: Record<string, string> = {
  pos: 'secondary',
  ubereats: 'dark',
  foodpanda: 'danger',
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

async function loadSales() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (dateFrom.value) params.date_from = dateFrom.value
    if (dateTo.value) params.date_to = dateTo.value
    if (cashierFilter.value) params.cashier = cashierFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    if (sourceFilter.value) params.source = sourceFilter.value
    const res = await http.get('/pos/sales', { params })
    sales.value = res.data.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

function openDetail(sale: PosSaleRecord) {
  selectedSale.value = sale
  refundReason.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedSale.value = null
}

async function doRefund() {
  if (!selectedSale.value) return
  if (!confirm('確定要退款此訂單？')) return
  refunding.value = true
  try {
    await http.post(`/pos/sales/${selectedSale.value._id}/refund`, {
      reason: refundReason.value.trim(),
    })
    toast.show('退款成功', 'success')
    closeModal()
    await loadSales()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '退款失敗', 'danger')
  } finally {
    refunding.value = false
  }
}

onMounted(() => {
  dateFrom.value = todayStr()
  dateTo.value = todayStr()
  loadSales()
})
</script>

<template>
  <div>
    <div class="table-card">
      <div class="table-header">
        <h6><i class="bi bi-receipt me-1"></i>銷售記錄</h6>
        <div class="toolbar flex-wrap">
          <select v-model="sourceFilter" class="form-select form-select-sm" style="width:120px">
            <option value="">全部來源</option>
            <option value="pos">POS 現場</option>
            <option value="ubereats">UberEats</option>
            <option value="foodpanda">foodpanda</option>
          </select>
          <input v-model="dateFrom" type="date" class="form-control form-control-sm" style="width:140px" />
          <span class="text-muted small">～</span>
          <input v-model="dateTo" type="date" class="form-control form-control-sm" style="width:140px" />
          <input
            v-model="cashierFilter"
            type="text"
            class="form-control form-control-sm"
            style="width:90px"
            placeholder="收銀員"
          />
          <select v-model="statusFilter" class="form-select form-select-sm" style="width:100px">
            <option value="">全部狀態</option>
            <option value="completed">已完成</option>
            <option value="refunded">已退款</option>
          </select>
          <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="loadSales">
            <i class="bi bi-search"></i>
          </button>
          <!-- 匯出 -->
          <button
            class="btn btn-sm btn-outline-success"
            :disabled="exporting"
            @click="exportCsv"
            title="依目前篩選條件匯出全部銷售記錄為 CSV"
          >
            <span v-if="exporting" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-download me-1"></i>匯出 CSV
          </button>
          <!-- 匯入 -->
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="importing"
            @click="openImport"
            title="從 CSV 或 JSON 匯入歷史銷售記錄（僅 admin，不扣庫存）"
          >
            <span v-if="importing" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-upload me-1"></i>匯入
          </button>
          <input
            ref="fileInput"
            type="file"
            accept=".csv,.json"
            style="display:none"
            @change="onFileChange"
          />
        </div>
      </div>

      <div class="table-responsive">
        <table class="table mb-0">
          <thead>
            <tr>
              <th>單號</th>
              <th>來源</th>
              <th>倉庫</th>
              <th>收銀員</th>
              <th class="text-end">件數</th>
              <th class="text-end">折扣</th>
              <th class="text-end">金額</th>
              <th>付款</th>
              <th>狀態</th>
              <th>時間</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="11" class="text-center py-3">
                <div class="spinner-border spinner-border-sm me-2"></div>載入中…
              </td>
            </tr>
            <tr v-else-if="!sales.length">
              <td colspan="11" class="text-center text-muted py-3">無銷售記錄</td>
            </tr>
            <tr v-for="s in sales" :key="s._id">
              <td class="fw-semibold small">{{ s.order_no }}</td>
              <td>
                <span :class="`badge bg-${SOURCE_COLOR[s.source || 'pos'] || 'secondary'}`">
                  {{ SOURCE_LABEL[s.source || 'pos'] || s.source }}
                </span>
              </td>
              <td class="small text-muted">{{ s.warehouse_name || '—' }}</td>
              <td class="small">{{ s.cashier || '—' }}</td>
              <td class="text-end small">
                {{ s.items?.reduce((acc: number, i: PosItem) => acc + i.quantity, 0) || 0 }}
              </td>
              <td class="text-end small text-muted">
                {{ s.discount > 0 ? `-$${Number(s.discount).toLocaleString()}` : '—' }}
              </td>
              <td class="text-end fw-bold text-primary">
                ${{ Number(s.total_amount || 0).toLocaleString() }}
              </td>
              <td class="small">{{ s.payment_type }}</td>
              <td>
                <span v-if="s.status === 'completed'" class="badge bg-success">已完成</span>
                <span v-else-if="s.status === 'refunded'" class="badge bg-secondary">已退款</span>
                <span v-else class="badge bg-warning text-dark">{{ s.status }}</span>
              </td>
              <td class="small text-muted">{{ fmtDate(s.created_at) }}</td>
              <td>
                <button class="btn btn-xs btn-outline-secondary" @click="openDetail(s)">
                  <i class="bi bi-eye"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail Modal -->
    <div
      v-if="showModal && selectedSale"
      class="modal fade show d-block"
      tabindex="-1"
      style="background: rgba(0,0,0,.5)"
      @click.self="closeModal"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">銷售單詳情 — {{ selectedSale.order_no }}</h5>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>
          <div class="modal-body">
            <table class="table table-sm mb-3">
              <thead>
                <tr>
                  <th>商品</th>
                  <th class="text-end">數量</th>
                  <th class="text-end">單價</th>
                  <th class="text-end">小計</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in selectedSale.items" :key="idx">
                  <td>
                    {{ item.product_name }}
                    <br />
                    <small class="text-muted">{{ item.product_sku }}</small>
                  </td>
                  <td class="text-end">{{ item.quantity }}</td>
                  <td class="text-end">${{ Number(item.unit_price).toLocaleString() }}</td>
                  <td class="text-end fw-bold">${{ Number(item.subtotal).toLocaleString() }}</td>
                </tr>
              </tbody>
            </table>
            <div class="small">
              <div class="d-flex justify-content-between mb-1">
                <span class="text-muted">小計</span>
                <span>${{ Number(selectedSale.subtotal || 0).toLocaleString() }}</span>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span class="text-muted">折扣</span>
                <span>-${{ Number(selectedSale.discount || 0).toLocaleString() }}</span>
              </div>
              <div class="d-flex justify-content-between fw-bold border-top pt-1 mt-1">
                <span>合計</span>
                <span class="text-primary">${{ Number(selectedSale.total_amount).toLocaleString() }}</span>
              </div>
            </div>
            <hr />
            <div class="small text-muted">
              <div>付款方式：{{ selectedSale.payment_type }}</div>
              <div v-if="(selectedSale.cash_amount ?? 0) > 0">
                收現：${{ Number(selectedSale.cash_amount).toLocaleString() }}
                · 找零：${{ Number(selectedSale.change_amount || 0).toLocaleString() }}
              </div>
              <div>倉庫：{{ selectedSale.warehouse_name || '—' }} · 收銀：{{ selectedSale.cashier || '—' }}</div>
              <div v-if="selectedSale.remark">備註：{{ selectedSale.remark }}</div>
            </div>
            <div v-if="selectedSale.status === 'completed'" class="mt-3">
              <label class="form-label small fw-semibold">退款原因（選填）</label>
              <input
                v-model="refundReason"
                type="text"
                class="form-control form-control-sm"
                placeholder="輸入退款原因…"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeModal">關閉</button>
            <button
              v-if="selectedSale.status === 'completed'"
              class="btn btn-outline-danger"
              :disabled="refunding"
              @click="doRefund"
            >
              <span v-if="refunding" class="spinner-border spinner-border-sm me-1"></span>
              退款
            </button>
            <span v-else class="badge bg-secondary py-2 px-3">已退款</span>
          </div>
        </div>
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
.btn-xs {
  padding: .15rem .4rem;
  font-size: .75rem;
}
</style>
