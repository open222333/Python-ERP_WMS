<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'
import http from '@/api'
import type { Warehouse } from '@/types'

const toast = useToastStore()

// ── Types ──────────────────────────────────────────────────
interface StockMovement {
  _id:             string
  sku:             string
  product_name:    string
  warehouse_name:  string
  movement_type:   string
  quantity:        number
  before_quantity: number
  after_quantity:  number
  remark:          string
  operator:        string
  created_at:      string
}

// ── State ──────────────────────────────────────────────────
const movements  = ref<StockMovement[]>([])
const warehouses = ref<Warehouse[]>([])
const loading    = ref(false)

const filterWhId  = ref('')
const filterType  = ref('')
const dateFrom    = ref('')
const dateTo      = ref('')

// ── Movement type map ──────────────────────────────────────
const MV_TYPES: Record<string, { label: string; cls: string }> = {
  inbound:      { label: '入庫',   cls: 'bg-success'          },
  outbound:     { label: '出庫',   cls: 'bg-danger'           },
  consume:      { label: '消耗',   cls: 'bg-warning text-dark'},
  transfer_in:  { label: '調撥入', cls: 'bg-info text-dark'   },
  transfer_out: { label: '調撥出', cls: 'bg-secondary'        },
  adjust:       { label: '盤點',   cls: 'bg-primary'          },
}

// ── API ────────────────────────────────────────────────────
async function loadWarehouses() {
  try {
    const { data } = await http.get('/warehouse/')
    warehouses.value = data.data ?? data ?? []
  } catch {
    toast.show('載入倉庫失敗', 'danger')
  }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterWhId.value) params.warehouse_id    = filterWhId.value
    if (filterType.value) params.movement_type   = filterType.value
    if (dateFrom.value)   params.date_from       = dateFrom.value
    if (dateTo.value)     params.date_to         = dateTo.value
    const { data } = await http.get('/inventory/movement/', { params })
    movements.value = data.data ?? data ?? []
  } catch {
    toast.show('載入紀錄失敗', 'danger')
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  filterWhId.value = ''
  filterType.value = ''
  dateFrom.value   = ''
  dateTo.value     = ''
  load()
}

onMounted(async () => {
  await Promise.all([loadWarehouses(), load()])
})
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-arrow-left-right me-1"></i>庫存移動紀錄</h6>
      <div class="toolbar flex-wrap">
        <!-- Warehouse filter -->
        <select
          v-model="filterWhId"
          class="form-select form-select-sm"
          style="width: 150px"
          @change="load"
        >
          <option value="">全部倉庫</option>
          <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
        </select>

        <!-- Type filter -->
        <select
          v-model="filterType"
          class="form-select form-select-sm"
          style="width: 130px"
          @change="load"
        >
          <option value="">全部類型</option>
          <option v-for="(v, k) in MV_TYPES" :key="k" :value="k">{{ v.label }}</option>
        </select>

        <!-- Date range -->
        <input
          v-model="dateFrom"
          type="date"
          class="form-control form-control-sm"
          style="width: 145px"
          @change="load"
          title="開始日期"
        />
        <span class="text-muted small">～</span>
        <input
          v-model="dateTo"
          type="date"
          class="form-control form-control-sm"
          style="width: 145px"
          @change="load"
          title="結束日期"
        />

        <button class="btn btn-sm btn-outline-secondary" @click="load" title="查詢">
          <i class="bi bi-search"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="clearFilters" title="清除篩選">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
    </div>

    <div class="table-responsive">
      <table class="table mb-0 table-sm">
        <thead>
          <tr>
            <th>SKU</th>
            <th>產品</th>
            <th>倉庫</th>
            <th>類型</th>
            <th class="text-end">數量</th>
            <th class="text-end">調整前</th>
            <th class="text-end">調整後</th>
            <th>備註</th>
            <th>操作人</th>
            <th>時間</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!movements.length">
            <td colspan="10" class="text-center text-muted py-3">無移動紀錄</td>
          </tr>
          <tr v-for="m in movements" :key="m._id">
            <td><code class="text-primary">{{ m.sku }}</code></td>
            <td>{{ m.product_name }}</td>
            <td>{{ m.warehouse_name }}</td>
            <td>
              <span
                class="badge"
                :class="MV_TYPES[m.movement_type]?.cls ?? 'bg-secondary'"
              >
                {{ MV_TYPES[m.movement_type]?.label ?? m.movement_type }}
              </span>
            </td>
            <td
              class="text-end fw-bold"
              :class="m.quantity >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ m.quantity >= 0 ? '+' : '' }}{{ m.quantity }}
            </td>
            <td class="text-end text-muted">{{ m.before_quantity }}</td>
            <td class="text-end text-muted">{{ m.after_quantity }}</td>
            <td class="text-muted" style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              {{ m.remark || '—' }}
            </td>
            <td>{{ m.operator || '—' }}</td>
            <td><small class="text-muted">{{ fmtDate(m.created_at) }}</small></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer count -->
    <div v-if="!loading && movements.length" class="px-3 py-2 border-top text-muted small">
      共 {{ movements.length }} 筆紀錄
    </div>
  </div>
</template>
