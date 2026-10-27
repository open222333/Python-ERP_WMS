<script setup>
import { ref, onMounted } from 'vue'
import { useToastStore }  from '@/stores/toast'
import { deliveryApi }    from '@/api/delivery'
import { fmtDate }        from '@/utils/format'
import LoadMore           from '@/components/LoadMore.vue'
import { appConfirm }     from '@/composables/useConfirm'

const toast  = useToastStore()
const orders = ref([])
const loading = ref(false)
const statusFilter = ref('')

// 與後端 src/constants.py DeliveryOrderStatus 一致。
// 原本頁面用 pending／accepted／delivering／completed，後端完全不認得：
// 篩選永遠查無資料、狀態徽章顯示原始英文、「接單／配送／完成」按鈕一律回 400。
const STATUS_MAP = {
  new:       { label: '新訂單', cls: 'badge-pending'   },
  confirmed: { label: '已接單', cls: 'badge-confirmed' },
  preparing: { label: '備餐中', cls: 'badge-confirmed' },
  ready:     { label: '待取餐', cls: 'bg-info text-white' },
  picked_up: { label: '配送中', cls: 'bg-info text-white' },
  delivered: { label: '已送達', cls: 'badge-completed' },
  cancelled: { label: '已取消', cls: 'badge-cancelled' },
}
// 下一步操作（狀態只能往前推進，見 DeliveryOrderStatus.is_valid_transition）
const NEXT_ACTION = {
  new:       { to: 'confirmed', label: '接單',   cls: 'btn-success' },
  confirmed: { to: 'preparing', label: '開始備餐', cls: 'btn-primary' },
  preparing: { to: 'ready',     label: '備妥',   cls: 'btn-primary' },
  ready:     { to: 'picked_up', label: '已取餐', cls: 'btn-info' },
  picked_up: { to: 'delivered', label: '已送達', cls: 'btn-outline-success' },
}
const CANCELLABLE = ['new', 'confirmed', 'preparing', 'ready', 'picked_up']
const PLATFORM_LABEL = { ubereats: 'Uber Eats', foodpanda: 'foodpanda' }

// [U3] 分頁：原本只拿到後端預設 200 筆且無提示
const PAGE_SIZE = 100
const hasMore = ref(false)

async function load(append = false) {
  loading.value = true
  try {
    const params = { limit: PAGE_SIZE, offset: append ? orders.value.length : 0 }
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await deliveryApi.getOrders(params)
    const page = data.data || data || []
    orders.value = append ? [...orders.value, ...page] : page
    hasMore.value = page.length === PAGE_SIZE
  } catch { toast.show('載入失敗', 'danger') }
  finally { loading.value = false }
}

async function updateStatus(o, status) {
  if (status === 'cancelled' &&
      !(await appConfirm(`確定要取消訂單 ${o.external_order_no || o.order_no}？已接單的訂單會作廢銷售紀錄並回補庫存。`,
                         { okText: '取消訂單', danger: true }))) return
  try {
    const { data } = await deliveryApi.updateOrderStatus(o._id, status)
    toast.show(data?.changed === false ? '狀態未變更' : '狀態已更新')
    if (data?.skipped_items?.length) toast.show(`未扣庫存：${data.skipped_items.join('、')}`, 'warning', 6000)
    await load()
  } catch (e) { toast.show(e?.response?.data?.message || '失敗', 'danger') }
}

onMounted(() => load())
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-scooter me-1"></i>外送訂單</h6>
      <div class="toolbar">
        <select v-model="statusFilter" class="form-select form-select-sm" style="width:130px" @change="load()">
          <option value="">全部狀態</option>
          <option v-for="(v,k) in STATUS_MAP" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <button class="btn btn-sm btn-outline-secondary" @click="load()" title="重新整理" aria-label="重新整理">
          <i class="bi bi-arrow-clockwise"></i>
        </button>
      </div>
    </div>
    <div class="table-responsive">
      <table v-stack-table class="table mb-0">
        <thead><tr><th>平台</th><th>訂單號</th><th>狀態</th><th class="text-end">金額</th><th>下單時間</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-if="loading && !orders.length"><td colspan="6" class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></td></tr>
          <tr v-else-if="!orders.length"><td colspan="6" class="text-center text-muted py-3">無外送訂單</td></tr>
          <tr v-for="o in orders" :key="o._id">
            <td>{{ PLATFORM_LABEL[o.platform] || o.platform || '-' }}</td>
            <td><code>{{ o.external_order_no || o.order_no || o._id?.slice(-6) }}</code></td>
            <td>
              <span class="order-status" :class="STATUS_MAP[o.status]?.cls">{{ STATUS_MAP[o.status]?.label || o.status }}</span>
              <div v-if="o.platform_status" class="text-muted" style="font-size:.7rem">平台：{{ o.platform_status }}</div>
            </td>
            <td class="text-end">${{ Number(o.total_amount||0).toFixed(0) }}</td>
            <td><small class="text-muted">{{ fmtDate(o.placed_at || o.created_at) }}</small></td>
            <td>
              <div class="d-flex gap-1 justify-content-end justify-content-md-start flex-wrap">
                <button v-if="NEXT_ACTION[o.status]" class="btn btn-xs" :class="NEXT_ACTION[o.status].cls"
                        @click="updateStatus(o, NEXT_ACTION[o.status].to)">{{ NEXT_ACTION[o.status].label }}</button>
                <button v-if="CANCELLABLE.includes(o.status)" class="btn btn-xs btn-outline-danger"
                        @click="updateStatus(o, 'cancelled')">{{ o.status === 'new' ? '拒單' : '取消' }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <LoadMore :count="orders.length" :has-more="hasMore" :loading="loading" @more="load(true)" />
  </div>
</template>

<style scoped>
.btn-xs { padding:.25rem .55rem; font-size:.78rem; }
.bg-info { background:#0dcaf0!important; }
</style>
