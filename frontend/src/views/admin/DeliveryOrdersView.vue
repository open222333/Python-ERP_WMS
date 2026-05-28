<script setup>
import { ref, onMounted } from 'vue'
import { useToastStore }  from '@/stores/toast'
import { deliveryApi }    from '@/api/delivery'

const toast  = useToastStore()
const orders = ref([])
const loading = ref(false)
const statusFilter = ref('')

const STATUS_MAP = {
  pending:   { label: '待接單', cls: 'badge-pending'   },
  accepted:  { label: '已接單', cls: 'badge-confirmed' },
  delivering:{ label: '配送中', cls: 'bg-info text-white' },
  completed: { label: '完成',   cls: 'badge-completed' },
  cancelled: { label: '取消',   cls: 'badge-cancelled' },
}

async function load() {
  loading.value = true
  try {
    const params = statusFilter.value ? { status: statusFilter.value } : {}
    const { data } = await deliveryApi.getOrders(params)
    orders.value = data.data || data || []
  } catch { toast.show('載入失敗', 'danger') }
  finally { loading.value = false }
}

async function updateStatus(id, status) {
  try {
    await deliveryApi.updateOrderStatus(id, status)
    toast.show('狀態已更新')
    await load()
  } catch (e) { toast.show(e?.response?.data?.message || '失敗', 'danger') }
}

onMounted(load)
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-scooter me-1"></i>外送訂單</h6>
      <div class="toolbar">
        <select v-model="statusFilter" class="form-select form-select-sm" style="width:130px" @change="load">
          <option value="">全部狀態</option>
          <option v-for="(v,k) in STATUS_MAP" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <button class="btn btn-sm btn-outline-secondary" @click="load"><i class="bi bi-arrow-clockwise"></i></button>
      </div>
    </div>
    <div class="table-responsive">
      <table class="table mb-0">
        <thead><tr><th>平台</th><th>訂單號</th><th>狀態</th><th class="text-end">金額</th><th>時間</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-if="loading"><td colspan="6" class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></td></tr>
          <tr v-else-if="!orders.length"><td colspan="6" class="text-center text-muted py-3">無外送訂單</td></tr>
          <tr v-for="o in orders" :key="o._id">
            <td>{{ o.platform || '-' }}</td>
            <td><code>{{ o.platform_order_id || o._id?.slice(-6) }}</code></td>
            <td><span class="order-status" :class="STATUS_MAP[o.status]?.cls">{{ STATUS_MAP[o.status]?.label || o.status }}</span></td>
            <td class="text-end">${{ Number(o.total_amount||0).toFixed(0) }}</td>
            <td><small class="text-muted">{{ o.created_at?.slice(0,16) || '-' }}</small></td>
            <td class="d-flex gap-1">
              <button v-if="o.status==='pending'" class="btn btn-xs btn-success" @click="updateStatus(o._id,'accepted')">接單</button>
              <button v-if="o.status==='accepted'" class="btn btn-xs btn-info" @click="updateStatus(o._id,'delivering')">配送</button>
              <button v-if="o.status==='delivering'" class="btn btn-xs btn-primary" @click="updateStatus(o._id,'completed')">完成</button>
              <button v-if="['pending','accepted'].includes(o.status)" class="btn btn-xs btn-danger" @click="updateStatus(o._id,'cancelled')">取消</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.btn-xs { padding:.15rem .4rem; font-size:.75rem; }
.bg-info { background:#0dcaf0!important; }
</style>
