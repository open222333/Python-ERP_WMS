<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'
import http from '@/api'
import type { Warehouse } from '@/types'

const toast = useToastStore()

// ── Types ──────────────────────────────────────────────────
// 後端欄位為 product_sku / before_qty / after_qty（見 src/models/inventory.py）；
// 原本頁面讀 sku / before_quantity / after_quantity，SKU 與調整前後一直是空白，已修正
interface StockMovement {
  _id:             string
  product_sku?:    string
  product_name:    string
  warehouse_name:  string
  movement_type:   string
  movement_label?: string
  quantity:        number
  before_qty?:     number
  after_qty?:      number
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

// [MOBILE] 小螢幕改卡片顯示，篩選列預設收合
const isMobile    = ref(false)
const showFilters = ref(false)
let mql: MediaQueryList | null = null
const onMql = (e: MediaQueryListEvent) => { isMobile.value = e.matches }

const activeFilterCount = computed(() =>
  [filterWhId.value, filterType.value, dateFrom.value, dateTo.value].filter(Boolean).length)

// ── Movement type map ──────────────────────────────────────
const MV_TYPES: Record<string, { label: string; cls: string }> = {
  inbound:      { label: '入庫',   cls: 'bg-success'          },
  outbound:     { label: '出庫',   cls: 'bg-danger'           },
  consume:      { label: '消耗',   cls: 'bg-warning text-dark'},
  transfer_in:  { label: '調撥入', cls: 'bg-info text-dark'   },
  transfer_out: { label: '調撥出', cls: 'bg-secondary'        },
  adjust:       { label: '盤點',   cls: 'bg-primary'          },
}
const typeLabel = (m: StockMovement) => MV_TYPES[m.movement_type]?.label ?? m.movement_label ?? m.movement_type
const typeCls   = (m: StockMovement) => MV_TYPES[m.movement_type]?.cls ?? 'bg-secondary'
const fmtQty    = (q: number) => (q >= 0 ? '+' : '') + q

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
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '載入紀錄失敗', 'danger')
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
  mql = window.matchMedia('(max-width: 767.98px)')
  isMobile.value = mql.matches
  mql.addEventListener('change', onMql)
  await Promise.all([loadWarehouses(), load()])
})
onBeforeUnmount(() => mql?.removeEventListener('change', onMql))
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6 class="mb-0"><i class="bi bi-arrow-left-right me-1"></i>庫存移動紀錄</h6>
      <button v-if="isMobile" class="btn btn-sm btn-outline-secondary filter-toggle"
              @click="showFilters = !showFilters">
        <i class="bi bi-funnel me-1"></i>篩選
        <span v-if="activeFilterCount" class="badge bg-primary ms-1">{{ activeFilterCount }}</span>
      </button>

      <div v-show="!isMobile || showFilters" class="toolbar flex-wrap" :class="{ 'mobile-filters': isMobile }">
        <!-- Warehouse filter -->
        <select v-model="filterWhId" class="form-select form-select-sm f-wh" @change="load">
          <option value="">全部倉庫</option>
          <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
        </select>

        <!-- Type filter -->
        <select v-model="filterType" class="form-select form-select-sm f-type" @change="load">
          <option value="">全部類型</option>
          <option v-for="(v, k) in MV_TYPES" :key="k" :value="k">{{ v.label }}</option>
        </select>

        <!-- Date range -->
        <div class="d-flex align-items-center gap-1 f-dates">
          <input v-model="dateFrom" type="date" class="form-control form-control-sm"
                 @change="load" title="開始日期" />
          <span class="text-muted small">～</span>
          <input v-model="dateTo" type="date" class="form-control form-control-sm"
                 @change="load" title="結束日期" />
        </div>

        <div class="d-flex gap-1 f-actions">
          <button class="btn btn-sm btn-outline-secondary" @click="load" title="查詢">
            <i class="bi bi-search"></i><span v-if="isMobile" class="ms-1">查詢</span>
          </button>
          <button class="btn btn-sm btn-outline-secondary" @click="clearFilters" title="清除篩選">
            <i class="bi bi-x-lg"></i><span v-if="isMobile" class="ms-1">清除</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── 手機：卡片列表 ─────────────────────────────── -->
    <div v-if="isMobile" class="mv-cards">
      <div v-if="loading" class="text-center py-4">
        <div class="spinner-border spinner-border-sm text-primary"></div>
      </div>
      <div v-else-if="!movements.length" class="text-center text-muted py-4">無移動紀錄</div>
      <template v-else>
      <div v-for="m in movements" :key="m._id" class="mv-card">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <div class="min-w-0">
            <div class="fw-semibold text-truncate">{{ m.product_name }}</div>
            <code v-if="m.product_sku" class="text-primary small">{{ m.product_sku }}</code>
          </div>
          <div class="text-end flex-shrink-0">
            <div class="mv-qty" :class="m.quantity >= 0 ? 'text-success' : 'text-danger'">
              {{ fmtQty(m.quantity) }}
            </div>
            <span class="badge" :class="typeCls(m)">{{ typeLabel(m) }}</span>
          </div>
        </div>
        <div class="mv-meta">
          <span><i class="bi bi-building me-1"></i>{{ m.warehouse_name || '—' }}</span>
          <span v-if="m.before_qty !== undefined">{{ m.before_qty }} → {{ m.after_qty }}</span>
        </div>
        <div class="mv-meta">
          <span><i class="bi bi-person me-1"></i>{{ m.operator || '—' }}</span>
          <span>{{ fmtDate(m.created_at) }}</span>
        </div>
        <div v-if="m.remark" class="mv-remark">{{ m.remark }}</div>
      </div>
      </template>
    </div>

    <!-- ── 桌機：表格 ─────────────────────────────────── -->
    <div v-else class="table-responsive">
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
            <td><code class="text-primary">{{ m.product_sku || '—' }}</code></td>
            <td>{{ m.product_name }}</td>
            <td>{{ m.warehouse_name }}</td>
            <td><span class="badge" :class="typeCls(m)">{{ typeLabel(m) }}</span></td>
            <td class="text-end fw-bold" :class="m.quantity >= 0 ? 'text-success' : 'text-danger'">
              {{ fmtQty(m.quantity) }}
            </td>
            <td class="text-end text-muted">{{ m.before_qty ?? '—' }}</td>
            <td class="text-end text-muted">{{ m.after_qty ?? '—' }}</td>
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

<style scoped>
.f-wh   { width: 150px; }
.f-type { width: 130px; }
.f-dates input { width: 145px; }

.filter-toggle { margin-left: auto; }
.mobile-filters { width: 100%; display: grid !important; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.mobile-filters .f-wh, .mobile-filters .f-type { width: 100%; }
.mobile-filters .f-dates { grid-column: 1 / -1; }
.mobile-filters .f-dates input { width: auto; flex: 1; min-width: 0; }
.mobile-filters .f-actions { grid-column: 1 / -1; }
.mobile-filters .f-actions .btn { flex: 1; min-height: 40px; }
/* iOS：字級小於 16px 的輸入框聚焦時會自動放大畫面 */
.mobile-filters select, .mobile-filters input { font-size: 16px; min-height: 40px; }

.mv-cards { padding: 8px; display: flex; flex-direction: column; gap: 8px; }
.mv-card {
  border: 1px solid var(--table-border, #e9ecef); border-radius: 10px;
  padding: 10px 12px; background: var(--card-bg, #fff);   /* [U8] 深色模式 */
}
.mv-qty { font-size: 1.15rem; font-weight: 700; line-height: 1.2; }
.mv-meta {
  display: flex; justify-content: space-between; gap: 8px;
  font-size: .8rem; color: #6c757d; margin-top: 4px;
}
.mv-remark {
  font-size: .8rem; color: var(--bs-secondary-color, #495057); margin-top: 6px;
  background: var(--bs-tertiary-bg, #f8f9fa); border-radius: 6px; padding: 4px 8px;
}
.min-w-0 { min-width: 0; }
</style>
