<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

// ── State ────────────────────────────────────────────────────
const loading   = ref(false)
const invoices  = ref<any[]>([])
const filterStatus    = ref('')
const filterDateFrom  = ref('')
const filterDateTo    = ref('')

const showVoidModal = ref(false)
const voidTarget    = ref<any>(null)
const voidReason    = ref('')
const voidLoading   = ref(false)

const showDetailModal = ref(false)
const detailItem      = ref<any>(null)

// ── Load ─────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const params: Record<string, string> = { limit: '200' }
    if (filterStatus.value)   params.status    = filterStatus.value
    if (filterDateFrom.value) params.date_from = filterDateFrom.value
    if (filterDateTo.value)   params.date_to   = filterDateTo.value
    const r = await http.get('/invoice/', { params })
    invoices.value = r.data.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Computed ─────────────────────────────────────────────────
const stats = computed(() => ({
  total:   invoices.value.length,
  issued:  invoices.value.filter(i => i.status === 'issued').length,
  voided:  invoices.value.filter(i => i.status === 'voided').length,
  error:   invoices.value.filter(i => i.status === 'error').length,
  pending: invoices.value.filter(i => i.status === 'pending').length,
}))

// ── Void ─────────────────────────────────────────────────────
function openVoid(inv: any) {
  voidTarget.value = inv
  voidReason.value = ''
  showVoidModal.value = true
}

async function confirmVoid() {
  if (!voidTarget.value) return
  voidLoading.value = true
  try {
    await http.post(`/invoice/${voidTarget.value._id}/void`, { reason: voidReason.value || '作廢' })
    toast.show(`發票 ${voidTarget.value.invoice_no} 已作廢`, 'success')
    showVoidModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '作廢失敗', 'danger')
  } finally {
    voidLoading.value = false
  }
}

// ── Detail ───────────────────────────────────────────────────
function openDetail(inv: any) {
  detailItem.value = inv
  showDetailModal.value = true
}

// ── Helpers ──────────────────────────────────────────────────
function statusBadge(s: string) {
  return {
    issued:  'bg-success',
    voided:  'bg-secondary',
    error:   'bg-danger',
    pending: 'bg-warning text-dark',
  }[s] ?? 'bg-secondary'
}

function statusLabel(s: string) {
  return { issued: '已開立', voided: '已作廢', error: '開立失敗', pending: '待開立' }[s] ?? s
}

function carrierLabel(type: string, num: string) {
  if (!type) return '無（紙本）'
  if (type === '1') return `手機條碼 ${num}`
  if (type === '2') return `自然人憑證 ${num}`
  return num || '—'
}

function fmtDate(s: string) {
  return s ? s.replace('T', ' ').slice(0, 16) : '—'
}
</script>

<template>
  <div class="container-fluid py-3 px-4">

    <!-- 標題 -->
    <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
      <h5 class="mb-0 fw-bold">
        <i class="bi bi-receipt-cutoff me-2 text-primary"></i>電子發票管理
      </h5>
      <RouterLink to="/admin/invoice-settings" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-gear me-1"></i>發票設定
      </RouterLink>
    </div>

    <!-- 統計卡 -->
    <div class="row g-3 mb-3">
      <div class="col-6 col-md-3">
        <div class="card text-center shadow-sm py-2">
          <div class="fs-4 fw-bold text-primary">{{ stats.issued }}</div>
          <small class="text-muted">已開立</small>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center shadow-sm py-2">
          <div class="fs-4 fw-bold text-secondary">{{ stats.voided }}</div>
          <small class="text-muted">已作廢</small>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center shadow-sm py-2">
          <div class="fs-4 fw-bold text-danger">{{ stats.error }}</div>
          <small class="text-muted">開立失敗</small>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card text-center shadow-sm py-2">
          <div class="fs-4 fw-bold text-warning">{{ stats.pending }}</div>
          <small class="text-muted">待開立</small>
        </div>
      </div>
    </div>

    <!-- 篩選 -->
    <div class="card mb-3 shadow-sm">
      <div class="card-body py-2">
        <div class="row g-2 align-items-end">
          <div class="col-auto">
            <select v-model="filterStatus" class="form-select form-select-sm" style="width:140px">
              <option value="">全部狀態</option>
              <option value="issued">已開立</option>
              <option value="voided">已作廢</option>
              <option value="error">開立失敗</option>
              <option value="pending">待開立</option>
            </select>
          </div>
          <div class="col-auto">
            <input v-model="filterDateFrom" type="date" class="form-control form-control-sm" />
          </div>
          <div class="col-auto"><span class="text-muted small">至</span></div>
          <div class="col-auto">
            <input v-model="filterDateTo" type="date" class="form-control form-control-sm" />
          </div>
          <div class="col-auto">
            <button class="btn btn-sm btn-primary" @click="load" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-search me-1"></i>查詢
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 發票列表 -->
    <div class="card shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>發票號碼</th>
              <th>訂單編號</th>
              <th>金額</th>
              <th>載具 / 統編</th>
              <th>狀態</th>
              <th>開立時間</th>
              <th class="text-center" style="width:120px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!invoices.length">
              <td colspan="7" class="text-center text-muted py-4">
                <i class="bi bi-inbox fs-2 d-block mb-1"></i>尚無發票記錄
              </td>
            </tr>
            <tr v-for="inv in invoices" :key="inv._id">
              <td>
                <span class="fw-semibold font-monospace">{{ inv.invoice_no || '—' }}</span>
                <small v-if="inv.random_no" class="text-muted d-block">隨機碼：{{ inv.random_no }}</small>
              </td>
              <td>
                <span class="font-monospace small">{{ inv.order_no }}</span>
              </td>
              <td>NT$ {{ inv.total_amount?.toLocaleString() }}</td>
              <td>
                <span v-if="inv.buyer_id" class="text-info">統編 {{ inv.buyer_id }}</span>
                <span v-else-if="inv.love_code" class="text-danger">
                  <i class="bi bi-heart-fill me-1"></i>{{ inv.love_code }}
                </span>
                <span v-else class="small text-muted">{{ carrierLabel(inv.carrier_type, inv.carrier_num) }}</span>
              </td>
              <td>
                <span class="badge" :class="statusBadge(inv.status)">
                  {{ statusLabel(inv.status) }}
                </span>
                <small v-if="inv.error_msg" class="text-danger d-block mt-1" style="max-width:160px;white-space:normal">{{ inv.error_msg }}</small>
              </td>
              <td><small class="text-muted">{{ fmtDate(inv.issued_at || inv.created_at) }}</small></td>
              <td class="text-center">
                <button class="btn btn-sm btn-outline-secondary me-1" @click="openDetail(inv)" title="詳情">
                  <i class="bi bi-eye"></i>
                </button>
                <button v-if="inv.status === 'issued'"
                        class="btn btn-sm btn-outline-danger" @click="openVoid(inv)" title="作廢">
                  <i class="bi bi-x-circle"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ── 作廢 Modal ─────────────────────────── -->
  <Teleport to="body">
    <div v-if="showVoidModal" class="modal d-block" style="background:rgba(0,0,0,.5)" @click.self="showVoidModal=false">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title text-danger"><i class="bi bi-x-circle me-1"></i>作廢發票</h5>
            <button class="btn-close" @click="showVoidModal=false"></button>
          </div>
          <div class="modal-body">
            <p>確定要作廢發票 <strong>{{ voidTarget?.invoice_no }}</strong>？此操作不可撤回。</p>
            <div>
              <label class="form-label small fw-semibold">作廢原因</label>
              <input v-model="voidReason" type="text" class="form-control form-control-sm" placeholder="輸入原因（選填）" />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showVoidModal=false">取消</button>
            <button class="btn btn-danger" :disabled="voidLoading" @click="confirmVoid">
              <span v-if="voidLoading" class="spinner-border spinner-border-sm me-1"></span>確認作廢
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── 詳情 Modal ─────────────────────────── -->
  <Teleport to="body">
    <div v-if="showDetailModal" class="modal d-block" style="background:rgba(0,0,0,.5)" @click.self="showDetailModal=false">
      <div class="modal-dialog modal-dialog-centered modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-receipt me-1"></i>
              {{ detailItem?.invoice_no || '發票詳情' }}
            </h5>
            <button class="btn-close" @click="showDetailModal=false"></button>
          </div>
          <div v-if="detailItem" class="modal-body">
            <div class="row g-3">
              <div class="col-sm-6">
                <div class="small text-muted">訂單編號</div>
                <div class="fw-semibold font-monospace">{{ detailItem.order_no }}</div>
              </div>
              <div class="col-sm-6">
                <div class="small text-muted">發票號碼</div>
                <div class="fw-semibold">{{ detailItem.invoice_no || '—' }}</div>
              </div>
              <div class="col-sm-3">
                <div class="small text-muted">隨機碼</div>
                <div>{{ detailItem.random_no || '—' }}</div>
              </div>
              <div class="col-sm-3">
                <div class="small text-muted">開立日期</div>
                <div>{{ detailItem.invoice_date || '—' }}</div>
              </div>
              <div class="col-sm-3">
                <div class="small text-muted">金額</div>
                <div class="fw-bold text-primary">NT$ {{ detailItem.total_amount?.toLocaleString() }}</div>
              </div>
              <div class="col-sm-3">
                <div class="small text-muted">狀態</div>
                <span class="badge" :class="statusBadge(detailItem.status)">{{ statusLabel(detailItem.status) }}</span>
              </div>
              <div class="col-sm-6">
                <div class="small text-muted">載具 / 統編</div>
                <div>
                  <template v-if="detailItem.buyer_id">統一編號：{{ detailItem.buyer_id }}</template>
                  <template v-else-if="detailItem.love_code">愛心碼：{{ detailItem.love_code }}</template>
                  <template v-else>{{ carrierLabel(detailItem.carrier_type, detailItem.carrier_num) }}</template>
                </div>
              </div>
              <div v-if="detailItem.customer_name || detailItem.customer_email" class="col-sm-6">
                <div class="small text-muted">買方資訊</div>
                <div>{{ detailItem.customer_name }} {{ detailItem.customer_email }}</div>
              </div>
              <div v-if="detailItem.error_msg" class="col-12">
                <div class="alert alert-danger small mb-0">{{ detailItem.error_msg }}</div>
              </div>
              <div v-if="detailItem.void_reason" class="col-12">
                <div class="small text-muted">作廢原因</div>
                <div>{{ detailItem.void_reason }} <span class="text-muted">（{{ detailItem.voided_by }}）</span></div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showDetailModal=false">關閉</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
