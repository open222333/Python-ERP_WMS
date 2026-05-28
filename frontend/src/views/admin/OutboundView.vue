<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { Warehouse } from '@/types'

const toast = useToastStore()

// ── Types ──────────────────────────────────────────────────
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

interface SimpleProduct {
  _id:  string
  name: string
  sku:  string
}

// ── State ──────────────────────────────────────────────────
const orders       = ref<OutboundOrder[]>([])
const warehouses   = ref<Warehouse[]>([])
const products     = ref<SimpleProduct[]>([])
const loading      = ref(false)
const saving       = ref(false)
const itemSaving   = ref(false)

const statusFilter = ref('')

// Create form
const showCreateModal = ref(false)
const createForm = ref({ warehouse_id: '', customer: '', remark: '' })

// Detail
const showDetail  = ref(false)
const detailOrder = ref<OutboundOrder | null>(null)
const detailItems = ref<OutboundItem[]>([])

// Add item form
const showItemModal = ref(false)
const itemForm = ref({ product_id: '', quantity: 1, unit_price: 0 })

// ── Status map ─────────────────────────────────────────────
const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  pending:   { label: '待處理', cls: 'badge-pending'   },
  confirmed: { label: '已確認', cls: 'badge-confirmed' },
  completed: { label: '已完成', cls: 'badge-completed' },
  cancelled: { label: '已取消', cls: 'badge-cancelled' },
}

// ── API ────────────────────────────────────────────────────
async function loadDeps() {
  const [wRes, pRes] = await Promise.allSettled([
    http.get('/warehouse/'),
    http.get('/product/'),
  ])
  if (wRes.status === 'fulfilled') warehouses.value = wRes.value.data.data ?? wRes.value.data ?? []
  if (pRes.status === 'fulfilled') products.value   = pRes.value.data.data ?? pRes.value.data ?? []
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await http.get('/outbound/', { params })
    orders.value = data.data ?? data ?? []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function openDetail(order: OutboundOrder) {
  detailOrder.value = order
  detailItems.value = []
  showDetail.value  = true
  try {
    const { data } = await http.get(`/api/outbound/${order._id}`)
    const detail = data.data ?? data
    detailOrder.value = detail
    detailItems.value = detail.items ?? []
  } catch {
    toast.show('載入詳情失敗', 'danger')
  }
}

async function doAction(action: string) {
  if (!detailOrder.value) return
  try {
    await http.post(`/api/outbound/${detailOrder.value._id}/${action}`)
    toast.show('操作成功', 'success')
    await openDetail(detailOrder.value)
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '操作失敗', 'danger')
  }
}

async function createOrder() {
  if (!createForm.value.warehouse_id) {
    toast.show('請選擇倉庫', 'danger')
    return
  }
  saving.value = true
  try {
    await http.post('/outbound/', createForm.value)
    toast.show('建立成功', 'success')
    showCreateModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '建立失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function addItem() {
  if (!itemForm.value.product_id || itemForm.value.quantity <= 0) {
    toast.show('請填寫產品與數量', 'danger')
    return
  }
  if (!detailOrder.value) return
  itemSaving.value = true
  try {
    await http.post(`/api/outbound/${detailOrder.value._id}/item`, itemForm.value)
    toast.show('已新增品項', 'success')
    showItemModal.value = false
    await openDetail(detailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '新增失敗', 'danger')
  } finally {
    itemSaving.value = false
  }
}

async function removeItem(itemId: string) {
  if (!confirm('確定要移除此品項？') || !detailOrder.value) return
  try {
    await http.delete(`/api/outbound/${detailOrder.value._id}/item/${itemId}`)
    toast.show('已移除', 'success')
    await openDetail(detailOrder.value)
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '移除失敗', 'danger')
  }
}

function openCreateModal() {
  createForm.value = { warehouse_id: '', customer: '', remark: '' }
  showCreateModal.value = true
}

function openItemModal() {
  itemForm.value = { product_id: '', quantity: 1, unit_price: 0 }
  showItemModal.value = true
}

onMounted(async () => {
  await loadDeps()
  await load()
})
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-box-arrow-up me-1"></i>出庫管理</h6>
      <div class="toolbar">
        <select
          v-model="statusFilter"
          class="form-select form-select-sm"
          style="width: 130px"
          @change="load"
        >
          <option value="">全部狀態</option>
          <option v-for="(v, k) in STATUS_MAP" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <button class="btn btn-sm btn-primary" @click="openCreateModal">
          <i class="bi bi-plus-lg"></i> 建立出庫單
        </button>
      </div>
    </div>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>單號</th>
            <th>客戶</th>
            <th>倉庫</th>
            <th>狀態</th>
            <th class="text-end">總金額</th>
            <th>建立者</th>
            <th>日期</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!orders.length">
            <td colspan="8" class="text-center text-muted py-3">無出庫單</td>
          </tr>
          <tr v-for="o in orders" :key="o._id">
            <td>
              <small class="text-muted">#</small>{{ o.order_no || o._id.slice(-6) }}
            </td>
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
              <button class="btn btn-sm btn-outline-primary" @click="openDetail(o)" title="查看">
                <i class="bi bi-eye"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <Teleport to="body">
    <!-- Create Modal -->
    <div
      v-if="showCreateModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.5); z-index: 1055;"
      @click.self="showCreateModal = false"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-1"></i>建立出庫單</h5>
            <button type="button" class="btn-close" @click="showCreateModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">
                出庫倉庫 <span class="text-danger">*</span>
              </label>
              <select v-model="createForm.warehouse_id" class="form-select">
                <option value="">— 選擇倉庫 —</option>
                <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">客戶</label>
              <input v-model="createForm.customer" type="text" class="form-control" placeholder="選填" />
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">備註</label>
              <textarea v-model="createForm.remark" class="form-control" rows="2" placeholder="選填"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showCreateModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="createOrder">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              建立
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div
      v-if="showDetail && detailOrder"
      class="modal d-block"
      style="background: rgba(0,0,0,.5); z-index: 1055;"
      @click.self="showDetail = false"
    >
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              出庫單 #{{ detailOrder.order_no || detailOrder._id.slice(-6) }}
              <span class="order-status ms-2" :class="STATUS_MAP[detailOrder.status]?.cls">
                {{ STATUS_MAP[detailOrder.status]?.label }}
              </span>
            </h5>
            <button type="button" class="btn-close" @click="showDetail = false"></button>
          </div>

          <div class="modal-body">
            <!-- Info row -->
            <div class="row g-2 mb-3 small text-muted">
              <div class="col-md-3">
                <i class="bi bi-building me-1"></i>{{ detailOrder.warehouse_name }}
              </div>
              <div class="col-md-3">
                <i class="bi bi-person me-1"></i>{{ detailOrder.customer || '未填' }}
              </div>
              <div class="col-md-3">
                <i class="bi bi-person-circle me-1"></i>{{ detailOrder.creator }}
              </div>
              <div class="col-md-3">
                <i class="bi bi-calendar me-1"></i>{{ detailOrder.created_at?.slice(0, 10) }}
              </div>
            </div>

            <!-- Action buttons -->
            <div class="mb-3 d-flex gap-2 flex-wrap">
              <button
                v-if="detailOrder.status === 'pending'"
                class="btn btn-sm btn-success"
                @click="doAction('confirm')"
              >
                <i class="bi bi-check-circle me-1"></i>確認
              </button>
              <button
                v-if="detailOrder.status === 'confirmed'"
                class="btn btn-sm btn-primary"
                @click="doAction('complete')"
              >
                <i class="bi bi-check2-all me-1"></i>完成出庫
              </button>
              <button
                v-if="['pending', 'confirmed'].includes(detailOrder.status)"
                class="btn btn-sm btn-danger"
                @click="doAction('cancel')"
              >
                <i class="bi bi-x-circle me-1"></i>取消
              </button>
              <button
                v-if="['pending', 'confirmed'].includes(detailOrder.status)"
                class="btn btn-sm btn-outline-primary ms-auto"
                @click="openItemModal"
              >
                <i class="bi bi-plus-lg me-1"></i>新增品項
              </button>
            </div>

            <!-- Items table -->
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>產品</th>
                    <th>單位</th>
                    <th class="text-end">預計數量</th>
                    <th class="text-end">實出數量</th>
                    <th class="text-end">單價</th>
                    <th class="text-end">小計</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!detailItems.length">
                    <td colspan="8" class="text-center text-muted py-2">尚無品項</td>
                  </tr>
                  <tr v-for="item in detailItems" :key="item._id">
                    <td><code class="text-primary">{{ item.sku }}</code></td>
                    <td>{{ item.product_name }}</td>
                    <td>{{ item.unit }}</td>
                    <td class="text-end">{{ item.expected_qty }}</td>
                    <td class="text-end">{{ item.shipped_qty ?? '—' }}</td>
                    <td class="text-end">${{ Number(item.unit_price ?? 0).toFixed(2) }}</td>
                    <td class="text-end">
                      ${{ Number(item.expected_qty * (item.unit_price ?? 0)).toFixed(2) }}
                    </td>
                    <td>
                      <button
                        v-if="['pending', 'confirmed'].includes(detailOrder.status)"
                        class="btn btn-sm btn-outline-danger"
                        @click="removeItem(item._id)"
                        title="移除"
                      >
                        <i class="bi bi-trash"></i>
                      </button>
                    </td>
                  </tr>
                </tbody>
                <tfoot v-if="detailItems.length">
                  <tr>
                    <td colspan="6" class="text-end fw-bold">總計</td>
                    <td class="text-end fw-bold text-primary">
                      ${{ detailItems.reduce((s, i) =>
                        s + i.expected_qty * (i.unit_price ?? 0), 0
                      ).toFixed(2) }}
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

    <!-- Add Item Modal -->
    <div
      v-if="showItemModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.55); z-index: 1060;"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">新增出庫品項</h5>
            <button type="button" class="btn-close" @click="showItemModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">
                產品 <span class="text-danger">*</span>
              </label>
              <select v-model="itemForm.product_id" class="form-select">
                <option value="">— 選擇產品 —</option>
                <option v-for="p in products" :key="p._id" :value="p._id">
                  {{ p.name }} ({{ p.sku }})
                </option>
              </select>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label fw-semibold">
                  數量 <span class="text-danger">*</span>
                </label>
                <input
                  v-model.number="itemForm.quantity"
                  type="number"
                  min="1"
                  class="form-control"
                />
              </div>
              <div class="col-6">
                <label class="form-label fw-semibold">單價</label>
                <div class="input-group">
                  <span class="input-group-text">$</span>
                  <input
                    v-model.number="itemForm.unit_price"
                    type="number"
                    step="0.01"
                    min="0"
                    class="form-control"
                  />
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showItemModal = false">取消</button>
            <button class="btn btn-primary" :disabled="itemSaving" @click="addItem">
              <span v-if="itemSaving" class="spinner-border spinner-border-sm me-1"></span>
              新增
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
