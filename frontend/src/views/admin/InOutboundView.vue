<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { Warehouse } from '@/types'

const toast = useToastStore()

// ── Tab ────────────────────────────────────────────────────
const activeTab = ref<'inbound' | 'outbound'>('inbound')

// ── Types ──────────────────────────────────────────────────
interface InboundOrder {
  _id:            string
  order_no:       string
  warehouse_id:   string
  warehouse_name: string
  supplier:       string
  status:         'pending' | 'confirmed' | 'completed' | 'cancelled'
  total_amount:   number
  creator:        string
  remark:         string
  created_at:     string
  items?:         InboundItem[]
}

interface InboundItem {
  _id:          string
  product_id:   string
  product_name: string
  sku:          string
  unit:         string
  expected_qty: number
  received_qty: number
  unit_price:   number
}

interface OutboundOrder {
  _id:            string
  order_no:       string
  warehouse_id:   string
  warehouse_name: string
  customer:       string
  status:         'pending' | 'confirmed' | 'completed' | 'cancelled'
  total_amount:   number
  creator:        string
  remark:         string
  created_at:     string
  items?:         OutboundItem[]
}

interface OutboundItem {
  _id:          string
  product_id:   string
  product_name: string
  sku:          string
  unit:         string
  expected_qty: number
  shipped_qty:  number | null
  unit_price:   number
}

interface SimpleProduct { _id: string; name: string; sku: string }

// ── Shared ─────────────────────────────────────────────────
const warehouses = ref<Warehouse[]>([])
const products   = ref<SimpleProduct[]>([])

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  pending:   { label: '待處理', cls: 'badge-pending'   },
  confirmed: { label: '已確認', cls: 'badge-confirmed' },
  completed: { label: '已完成', cls: 'badge-completed' },
  cancelled: { label: '已取消', cls: 'badge-cancelled' },
}

async function loadDeps() {
  const [wRes, pRes] = await Promise.allSettled([
    http.get('/warehouse/'),
    http.get('/product/'),
  ])
  if (wRes.status === 'fulfilled') warehouses.value = wRes.value.data.data ?? wRes.value.data ?? []
  if (pRes.status === 'fulfilled') products.value   = pRes.value.data.data ?? pRes.value.data ?? []
}

// ── Inbound State ──────────────────────────────────────────
const inOrders        = ref<InboundOrder[]>([])
const inLoading       = ref(false)
const inSaving        = ref(false)
const inItemSaving    = ref(false)
const inStatusFilter  = ref('')
const showInCreate    = ref(false)
const inCreateForm    = ref({ warehouse_id: '', supplier: '', remark: '' })
const showInDetail    = ref(false)
const inDetailOrder   = ref<InboundOrder | null>(null)
const inDetailItems   = ref<InboundItem[]>([])
const showInItemModal = ref(false)
const inItemForm      = ref({ product_id: '', quantity: 1, unit_price: 0 })

async function loadInbound() {
  inLoading.value = true
  try {
    const params: Record<string, string> = {}
    if (inStatusFilter.value) params.status = inStatusFilter.value
    const { data } = await http.get('/inbound/', { params })
    inOrders.value = data.data ?? data ?? []
  } catch {
    toast.show('載入入庫單失敗', 'danger')
  } finally {
    inLoading.value = false
  }
}

async function openInDetail(order: InboundOrder) {
  inDetailOrder.value = order
  inDetailItems.value = []
  showInDetail.value  = true
  try {
    const { data } = await http.get(`/inbound/${order._id}`)
    const detail = data.data ?? data
    inDetailOrder.value = detail
    inDetailItems.value = detail.items ?? []
  } catch {
    toast.show('載入詳情失敗', 'danger')
  }
}

async function doInAction(action: string) {
  if (!inDetailOrder.value) return
  try {
    await http.post(`/inbound/${inDetailOrder.value._id}/${action}`)
    toast.show('操作成功', 'success')
    await openInDetail(inDetailOrder.value)
    await loadInbound()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '操作失敗', 'danger')
  }
}

async function createInbound() {
  if (!inCreateForm.value.warehouse_id) { toast.show('請選擇倉庫', 'danger'); return }
  inSaving.value = true
  try {
    await http.post('/inbound/', inCreateForm.value)
    toast.show('建立成功', 'success')
    showInCreate.value = false
    await loadInbound()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '建立失敗', 'danger')
  } finally {
    inSaving.value = false
  }
}

async function addInItem() {
  if (!inItemForm.value.product_id || inItemForm.value.quantity <= 0) {
    toast.show('請填寫產品與數量', 'danger'); return
  }
  if (!inDetailOrder.value) return
  inItemSaving.value = true
  try {
    await http.post(`/inbound/${inDetailOrder.value._id}/item`, inItemForm.value)
    toast.show('已新增品項', 'success')
    showInItemModal.value = false
    await openInDetail(inDetailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '新增失敗', 'danger')
  } finally {
    inItemSaving.value = false
  }
}

async function removeInItem(itemId: string) {
  if (!confirm('確定要移除此品項？') || !inDetailOrder.value) return
  try {
    await http.delete(`/inbound/${inDetailOrder.value._id}/item/${itemId}`)
    toast.show('已移除', 'success')
    await openInDetail(inDetailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '移除失敗', 'danger')
  }
}

// ── Outbound State ─────────────────────────────────────────
const outOrders        = ref<OutboundOrder[]>([])
const outLoading       = ref(false)
const outSaving        = ref(false)
const outItemSaving    = ref(false)
const outStatusFilter  = ref('')
const showOutCreate    = ref(false)
const outCreateForm    = ref({ warehouse_id: '', customer: '', remark: '' })
const showOutDetail    = ref(false)
const outDetailOrder   = ref<OutboundOrder | null>(null)
const outDetailItems   = ref<OutboundItem[]>([])
const showOutItemModal = ref(false)
const outItemForm      = ref({ product_id: '', quantity: 1, unit_price: 0 })

async function loadOutbound() {
  outLoading.value = true
  try {
    const params: Record<string, string> = {}
    if (outStatusFilter.value) params.status = outStatusFilter.value
    const { data } = await http.get('/outbound/', { params })
    outOrders.value = data.data ?? data ?? []
  } catch {
    toast.show('載入出庫單失敗', 'danger')
  } finally {
    outLoading.value = false
  }
}

async function openOutDetail(order: OutboundOrder) {
  outDetailOrder.value = order
  outDetailItems.value = []
  showOutDetail.value  = true
  try {
    const { data } = await http.get(`/outbound/${order._id}`)
    const detail = data.data ?? data
    outDetailOrder.value = detail
    outDetailItems.value = detail.items ?? []
  } catch {
    toast.show('載入詳情失敗', 'danger')
  }
}

async function doOutAction(action: string) {
  if (!outDetailOrder.value) return
  try {
    await http.post(`/outbound/${outDetailOrder.value._id}/${action}`)
    toast.show('操作成功', 'success')
    await openOutDetail(outDetailOrder.value)
    await loadOutbound()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '操作失敗', 'danger')
  }
}

async function createOutbound() {
  if (!outCreateForm.value.warehouse_id) { toast.show('請選擇倉庫', 'danger'); return }
  outSaving.value = true
  try {
    await http.post('/outbound/', outCreateForm.value)
    toast.show('建立成功', 'success')
    showOutCreate.value = false
    await loadOutbound()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '建立失敗', 'danger')
  } finally {
    outSaving.value = false
  }
}

async function addOutItem() {
  if (!outItemForm.value.product_id || outItemForm.value.quantity <= 0) {
    toast.show('請填寫產品與數量', 'danger'); return
  }
  if (!outDetailOrder.value) return
  outItemSaving.value = true
  try {
    await http.post(`/outbound/${outDetailOrder.value._id}/item`, outItemForm.value)
    toast.show('已新增品項', 'success')
    showOutItemModal.value = false
    await openOutDetail(outDetailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '新增失敗', 'danger')
  } finally {
    outItemSaving.value = false
  }
}

async function removeOutItem(itemId: string) {
  if (!confirm('確定要移除此品項？') || !outDetailOrder.value) return
  try {
    await http.delete(`/outbound/${outDetailOrder.value._id}/item/${itemId}`)
    toast.show('已移除', 'success')
    await openOutDetail(outDetailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '移除失敗', 'danger')
  }
}

onMounted(async () => {
  await loadDeps()
  await Promise.all([loadInbound(), loadOutbound()])
})
</script>

<template>
  <div class="table-card">
    <!-- Tab Header -->
    <div class="table-header">
      <div class="btn-group btn-group-sm">
        <button
          class="btn"
          :class="activeTab === 'inbound' ? 'btn-primary active' : 'btn-outline-secondary'"
          @click="activeTab = 'inbound'"
        >
          <i class="bi bi-box-arrow-in-down me-1"></i>入庫管理
        </button>
        <button
          class="btn"
          :class="activeTab === 'outbound' ? 'btn-primary active' : 'btn-outline-secondary'"
          @click="activeTab = 'outbound'"
        >
          <i class="bi bi-box-arrow-up me-1"></i>出庫管理
        </button>
      </div>

      <!-- Inbound toolbar -->
      <div v-if="activeTab === 'inbound'" class="d-flex gap-2 align-items-center">
        <select v-model="inStatusFilter" class="form-select form-select-sm" style="width:130px" @change="loadInbound">
          <option value="">全部狀態</option>
          <option v-for="(v, k) in STATUS_MAP" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <button class="btn btn-sm btn-primary" @click="showInCreate = true; inCreateForm = { warehouse_id: '', supplier: '', remark: '' }">
          <i class="bi bi-plus-lg"></i> 建立入庫單
        </button>
      </div>

      <!-- Outbound toolbar -->
      <div v-if="activeTab === 'outbound'" class="d-flex gap-2 align-items-center">
        <select v-model="outStatusFilter" class="form-select form-select-sm" style="width:130px" @change="loadOutbound">
          <option value="">全部狀態</option>
          <option v-for="(v, k) in STATUS_MAP" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <button class="btn btn-sm btn-primary" @click="showOutCreate = true; outCreateForm = { warehouse_id: '', customer: '', remark: '' }">
          <i class="bi bi-plus-lg"></i> 建立出庫單
        </button>
      </div>
    </div>

    <!-- ── 入庫 Tab ── -->
    <div v-if="activeTab === 'inbound'" class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>單號</th><th>供應商</th><th>倉庫</th><th>狀態</th>
            <th class="text-end">總金額</th><th>建立者</th><th>日期</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="inLoading">
            <td colspan="8" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></td>
          </tr>
          <tr v-else-if="!inOrders.length">
            <td colspan="8" class="text-center text-muted py-3">無入庫單</td>
          </tr>
          <tr v-for="o in inOrders" :key="o._id">
            <td><small class="text-muted">#</small>{{ o.order_no || o._id.slice(-6) }}</td>
            <td>{{ o.supplier || '—' }}</td>
            <td>{{ o.warehouse_name || '—' }}</td>
            <td>
              <span class="order-status" :class="STATUS_MAP[o.status]?.cls">
                {{ STATUS_MAP[o.status]?.label || o.status }}
              </span>
            </td>
            <td class="text-end">${{ Number(o.total_amount ?? 0).toFixed(2) }}</td>
            <td>{{ o.creator || '—' }}</td>
            <td><small class="text-muted">{{ o.created_at?.slice(0, 10) || '—' }}</small></td>
            <td>
              <button class="btn btn-sm btn-outline-primary" @click="openInDetail(o)" title="查看">
                <i class="bi bi-eye"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 出庫 Tab ── -->
    <div v-if="activeTab === 'outbound'" class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>單號</th><th>客戶</th><th>倉庫</th><th>狀態</th>
            <th class="text-end">總金額</th><th>建立者</th><th>日期</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="outLoading">
            <td colspan="8" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></td>
          </tr>
          <tr v-else-if="!outOrders.length">
            <td colspan="8" class="text-center text-muted py-3">無出庫單</td>
          </tr>
          <tr v-for="o in outOrders" :key="o._id">
            <td><small class="text-muted">#</small>{{ o.order_no || o._id.slice(-6) }}</td>
            <td>{{ o.customer || '—' }}</td>
            <td>{{ o.warehouse_name || '—' }}</td>
            <td>
              <span class="order-status" :class="STATUS_MAP[o.status]?.cls">
                {{ STATUS_MAP[o.status]?.label || o.status }}
              </span>
            </td>
            <td class="text-end">${{ Number(o.total_amount ?? 0).toFixed(2) }}</td>
            <td>{{ o.creator || '—' }}</td>
            <td><small class="text-muted">{{ o.created_at?.slice(0, 10) || '—' }}</small></td>
            <td>
              <button class="btn btn-sm btn-outline-primary" @click="openOutDetail(o)" title="查看">
                <i class="bi bi-eye"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <Teleport to="body">

    <!-- ── 入庫：建立 Modal ── -->
    <div v-if="showInCreate" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055" @click.self="showInCreate = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-1"></i>建立入庫單</h5>
            <button type="button" class="btn-close" @click="showInCreate = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">入庫倉庫 <span class="text-danger">*</span></label>
              <select v-model="inCreateForm.warehouse_id" class="form-select">
                <option value="">— 選擇倉庫 —</option>
                <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">供應商</label>
              <input v-model="inCreateForm.supplier" type="text" class="form-control" placeholder="選填" />
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">備註</label>
              <textarea v-model="inCreateForm.remark" class="form-control" rows="2" placeholder="選填"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showInCreate = false">取消</button>
            <button class="btn btn-primary" :disabled="inSaving" @click="createInbound">
              <span v-if="inSaving" class="spinner-border spinner-border-sm me-1"></span>建立
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 入庫：詳情 Modal ── -->
    <div v-if="showInDetail && inDetailOrder" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055" @click.self="showInDetail = false">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              入庫單 #{{ inDetailOrder.order_no || inDetailOrder._id.slice(-6) }}
              <span class="order-status ms-2" :class="STATUS_MAP[inDetailOrder.status]?.cls">
                {{ STATUS_MAP[inDetailOrder.status]?.label }}
              </span>
            </h5>
            <button type="button" class="btn-close" @click="showInDetail = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-2 mb-3 small text-muted">
              <div class="col-md-3"><i class="bi bi-building me-1"></i>{{ inDetailOrder.warehouse_name }}</div>
              <div class="col-md-3"><i class="bi bi-truck me-1"></i>{{ inDetailOrder.supplier || '未填' }}</div>
              <div class="col-md-3"><i class="bi bi-person-circle me-1"></i>{{ inDetailOrder.creator }}</div>
              <div class="col-md-3"><i class="bi bi-calendar me-1"></i>{{ inDetailOrder.created_at?.slice(0, 10) }}</div>
            </div>
            <div class="mb-3 d-flex gap-2 flex-wrap">
              <button v-if="inDetailOrder.status === 'pending'" class="btn btn-sm btn-success" @click="doInAction('confirm')">
                <i class="bi bi-check-circle me-1"></i>確認
              </button>
              <button v-if="inDetailOrder.status === 'confirmed'" class="btn btn-sm btn-primary" @click="doInAction('complete')">
                <i class="bi bi-check2-all me-1"></i>完成入庫
              </button>
              <button v-if="['pending','confirmed'].includes(inDetailOrder.status)" class="btn btn-sm btn-danger" @click="doInAction('cancel')">
                <i class="bi bi-x-circle me-1"></i>取消
              </button>
              <button v-if="['pending','confirmed'].includes(inDetailOrder.status)" class="btn btn-sm btn-outline-primary ms-auto"
                      @click="showInItemModal = true; inItemForm = { product_id: '', quantity: 1, unit_price: 0 }">
                <i class="bi bi-plus-lg me-1"></i>新增品項
              </button>
            </div>
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead>
                  <tr>
                    <th>SKU</th><th>產品</th><th>單位</th>
                    <th class="text-end">預計數量</th><th class="text-end">實收數量</th>
                    <th class="text-end">單價</th><th class="text-end">小計</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!inDetailItems.length">
                    <td colspan="8" class="text-center text-muted py-2">尚無品項</td>
                  </tr>
                  <tr v-for="item in inDetailItems" :key="item._id">
                    <td><code class="text-primary">{{ item.sku }}</code></td>
                    <td>{{ item.product_name }}</td>
                    <td>{{ item.unit }}</td>
                    <td class="text-end">{{ item.expected_qty }}</td>
                    <td class="text-end">{{ item.received_qty }}</td>
                    <td class="text-end">${{ Number(item.unit_price ?? 0).toFixed(2) }}</td>
                    <td class="text-end">${{ Number((item.received_qty || item.expected_qty) * (item.unit_price ?? 0)).toFixed(2) }}</td>
                    <td>
                      <button v-if="['pending','confirmed'].includes(inDetailOrder.status)"
                              class="btn btn-sm btn-outline-danger" @click="removeInItem(item._id)">
                        <i class="bi bi-trash"></i>
                      </button>
                    </td>
                  </tr>
                </tbody>
                <tfoot v-if="inDetailItems.length">
                  <tr>
                    <td colspan="6" class="text-end fw-bold">總計</td>
                    <td class="text-end fw-bold text-primary">
                      ${{ inDetailItems.reduce((s, i) => s + (i.received_qty || i.expected_qty) * (i.unit_price ?? 0), 0).toFixed(2) }}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 入庫：新增品項 Modal ── -->
    <div v-if="showInItemModal" class="modal d-block" style="background:rgba(0,0,0,.55);z-index:1060">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">新增入庫品項</h5>
            <button type="button" class="btn-close" @click="showInItemModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">產品 <span class="text-danger">*</span></label>
              <select v-model="inItemForm.product_id" class="form-select">
                <option value="">— 選擇產品 —</option>
                <option v-for="p in products" :key="p._id" :value="p._id">{{ p.name }} ({{ p.sku }})</option>
              </select>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label fw-semibold">數量 <span class="text-danger">*</span></label>
                <input v-model.number="inItemForm.quantity" type="number" min="1" class="form-control" />
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">單價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input v-model.number="inItemForm.unit_price" type="number" step="0.01" min="0" class="form-control" />
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showInItemModal = false">取消</button>
            <button class="btn btn-primary" :disabled="inItemSaving" @click="addInItem">
              <span v-if="inItemSaving" class="spinner-border spinner-border-sm me-1"></span>新增
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 出庫：建立 Modal ── -->
    <div v-if="showOutCreate" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055" @click.self="showOutCreate = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-1"></i>建立出庫單</h5>
            <button type="button" class="btn-close" @click="showOutCreate = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">出庫倉庫 <span class="text-danger">*</span></label>
              <select v-model="outCreateForm.warehouse_id" class="form-select">
                <option value="">— 選擇倉庫 —</option>
                <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">客戶</label>
              <input v-model="outCreateForm.customer" type="text" class="form-control" placeholder="選填" />
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">備註</label>
              <textarea v-model="outCreateForm.remark" class="form-control" rows="2" placeholder="選填"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showOutCreate = false">取消</button>
            <button class="btn btn-primary" :disabled="outSaving" @click="createOutbound">
              <span v-if="outSaving" class="spinner-border spinner-border-sm me-1"></span>建立
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 出庫：詳情 Modal ── -->
    <div v-if="showOutDetail && outDetailOrder" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055" @click.self="showOutDetail = false">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              出庫單 #{{ outDetailOrder.order_no || outDetailOrder._id.slice(-6) }}
              <span class="order-status ms-2" :class="STATUS_MAP[outDetailOrder.status]?.cls">
                {{ STATUS_MAP[outDetailOrder.status]?.label }}
              </span>
            </h5>
            <button type="button" class="btn-close" @click="showOutDetail = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-2 mb-3 small text-muted">
              <div class="col-md-3"><i class="bi bi-building me-1"></i>{{ outDetailOrder.warehouse_name }}</div>
              <div class="col-md-3"><i class="bi bi-person me-1"></i>{{ outDetailOrder.customer || '未填' }}</div>
              <div class="col-md-3"><i class="bi bi-person-circle me-1"></i>{{ outDetailOrder.creator }}</div>
              <div class="col-md-3"><i class="bi bi-calendar me-1"></i>{{ outDetailOrder.created_at?.slice(0, 10) }}</div>
            </div>
            <div class="mb-3 d-flex gap-2 flex-wrap">
              <button v-if="outDetailOrder.status === 'pending'" class="btn btn-sm btn-success" @click="doOutAction('confirm')">
                <i class="bi bi-check-circle me-1"></i>確認
              </button>
              <button v-if="outDetailOrder.status === 'confirmed'" class="btn btn-sm btn-primary" @click="doOutAction('complete')">
                <i class="bi bi-check2-all me-1"></i>完成出庫
              </button>
              <button v-if="['pending','confirmed'].includes(outDetailOrder.status)" class="btn btn-sm btn-danger" @click="doOutAction('cancel')">
                <i class="bi bi-x-circle me-1"></i>取消
              </button>
              <button v-if="['pending','confirmed'].includes(outDetailOrder.status)" class="btn btn-sm btn-outline-primary ms-auto"
                      @click="showOutItemModal = true; outItemForm = { product_id: '', quantity: 1, unit_price: 0 }">
                <i class="bi bi-plus-lg me-1"></i>新增品項
              </button>
            </div>
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead>
                  <tr>
                    <th>SKU</th><th>產品</th><th>單位</th>
                    <th class="text-end">預計數量</th><th class="text-end">實出數量</th>
                    <th class="text-end">單價</th><th class="text-end">小計</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!outDetailItems.length">
                    <td colspan="8" class="text-center text-muted py-2">尚無品項</td>
                  </tr>
                  <tr v-for="item in outDetailItems" :key="item._id">
                    <td><code class="text-primary">{{ item.sku }}</code></td>
                    <td>{{ item.product_name }}</td>
                    <td>{{ item.unit }}</td>
                    <td class="text-end">{{ item.expected_qty }}</td>
                    <td class="text-end">{{ item.shipped_qty ?? '—' }}</td>
                    <td class="text-end">${{ Number(item.unit_price ?? 0).toFixed(2) }}</td>
                    <td class="text-end">${{ Number(item.expected_qty * (item.unit_price ?? 0)).toFixed(2) }}</td>
                    <td>
                      <button v-if="['pending','confirmed'].includes(outDetailOrder.status)"
                              class="btn btn-sm btn-outline-danger" @click="removeOutItem(item._id)">
                        <i class="bi bi-trash"></i>
                      </button>
                    </td>
                  </tr>
                </tbody>
                <tfoot v-if="outDetailItems.length">
                  <tr>
                    <td colspan="6" class="text-end fw-bold">總計</td>
                    <td class="text-end fw-bold text-primary">
                      ${{ outDetailItems.reduce((s, i) => s + i.expected_qty * (i.unit_price ?? 0), 0).toFixed(2) }}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 出庫：新增品項 Modal ── -->
    <div v-if="showOutItemModal" class="modal d-block" style="background:rgba(0,0,0,.55);z-index:1060">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">新增出庫品項</h5>
            <button type="button" class="btn-close" @click="showOutItemModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">產品 <span class="text-danger">*</span></label>
              <select v-model="outItemForm.product_id" class="form-select">
                <option value="">— 選擇產品 —</option>
                <option v-for="p in products" :key="p._id" :value="p._id">{{ p.name }} ({{ p.sku }})</option>
              </select>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label fw-semibold">數量 <span class="text-danger">*</span></label>
                <input v-model.number="outItemForm.quantity" type="number" min="1" class="form-control" />
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">單價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input v-model.number="outItemForm.unit_price" type="number" step="0.01" min="0" class="form-control" />
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showOutItemModal = false">取消</button>
            <button class="btn btn-primary" :disabled="outItemSaving" @click="addOutItem">
              <span v-if="outItemSaving" class="spinner-border spinner-border-sm me-1"></span>新增
            </button>
          </div>
        </div>
      </div>
    </div>

  </Teleport>
</template>
