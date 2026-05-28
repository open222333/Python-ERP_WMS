<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'
import http from '@/api'
import type { Warehouse, InventoryItem } from '@/types'

const toast = useToastStore()

// ── State ──────────────────────────────────────────────────
const inventory   = ref<InventoryItem[]>([])
const warehouses  = ref<Warehouse[]>([])
const loading     = ref(false)
const filterWhId  = ref('')
const searchKw    = ref('')

// ── Computed ───────────────────────────────────────────────
const filteredInventory = computed(() => {
  let list = inventory.value
  if (filterWhId.value) {
    list = list.filter(i => i.warehouse_id === filterWhId.value)
  }
  if (searchKw.value.trim()) {
    const kw = searchKw.value.trim().toLowerCase()
    list = list.filter(i =>
      i.product_name.toLowerCase().includes(kw) ||
      i.sku.toLowerCase().includes(kw)
    )
  }
  return list
})

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
    if (filterWhId.value) params.warehouse_id = filterWhId.value
    const { data } = await http.get('/inventory/', { params })
    inventory.value = data.data ?? data ?? []
  } catch {
    toast.show('載入庫存失敗', 'danger')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadWarehouses(), load()])
})
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-archive me-1"></i>庫存查詢</h6>
      <div class="toolbar">
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

        <!-- Keyword search -->
        <input
          v-model="searchKw"
          type="text"
          class="form-control form-control-sm"
          style="width: 180px"
          placeholder="搜尋產品名稱/SKU"
        />
        <button class="btn btn-sm btn-outline-secondary" @click="load" title="刷新">
          <i class="bi bi-arrow-clockwise"></i>
        </button>
      </div>
    </div>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>產品名稱</th>
            <th>SKU</th>
            <th>倉庫</th>
            <th class="text-end">數量</th>
            <th>單位</th>
            <th>更新時間</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!filteredInventory.length">
            <td colspan="6" class="text-center text-muted py-3">無庫存資料</td>
          </tr>
          <tr v-for="inv in filteredInventory" :key="inv._id">
            <td class="fw-semibold">{{ inv.product_name }}</td>
            <td><code class="text-primary">{{ inv.sku }}</code></td>
            <td>{{ inv.warehouse_name }}</td>
            <td
              class="text-end fw-bold"
              :class="{ 'text-danger': inv.quantity === 0 }"
            >
              {{ inv.quantity.toLocaleString() }}
            </td>
            <td>{{ inv.unit }}</td>
            <td>
              <small class="text-muted">{{ fmtDate(inv.updated_at) }}</small>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer summary -->
    <div v-if="!loading && filteredInventory.length" class="px-3 py-2 border-top text-muted small">
      共 {{ filteredInventory.length }} 筆紀錄
      <span class="ms-3">
        庫存總量：
        <strong>{{ filteredInventory.reduce((s, i) => s + i.quantity, 0).toLocaleString() }}</strong>
      </span>
    </div>
  </div>
</template>
