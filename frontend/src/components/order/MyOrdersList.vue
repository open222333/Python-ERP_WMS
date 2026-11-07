<!-- [U10] 自 views/OrderView.vue 拆出 -->
<script setup lang="ts">
// 顧客「我的訂單」狀態（SSE 即時更新）
defineProps<{ orders: any[] }>()

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '等待中', processing: '製作中', completed: '已完成', cancelled: '已取消',
  }
  return map[s] || s
}

function statusBadge(s: string): string {
  const map: Record<string, string> = {
    pending: 'bg-warning text-dark', processing: 'bg-info text-dark',
    completed: 'bg-success', cancelled: 'bg-secondary',
  }
  return map[s] || 'bg-secondary'
}
</script>

<template>
  <div v-if="orders.length" class="order-status-section">
    <div class="order-status-title">
      <i class="bi bi-receipt me-1"></i>我的訂單
    </div>
    <div v-for="o in orders" :key="o._id" class="osc">
      <div class="d-flex justify-content-between align-items-center">
        <span class="osc-no">#{{ o.order_no }}</span>
        <span :class="`badge ${statusBadge(o.status)}`">{{ statusLabel(o.status) }}</span>
      </div>
      <div class="osc-items">
        {{ o.items.slice(0, 3).map((i: any) => i.item_name).join('、') }}
        <span v-if="o.items.length > 3">…</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 訂單狀態區塊 ─────────────────────────────── */
.order-status-section {
  padding-top: .75rem;
  border-top: 1px solid #e2e8f0;
}
.order-status-title {
  font-weight: 700;
  font-size: .78rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: .03em;
  margin-bottom: .5rem;
}
.osc {
  background: #f8fafc;
  border-radius: .5rem;
  padding: .45rem .6rem;
  margin-bottom: .35rem;
}
.osc-no    { font-weight: 700; font-size: .8rem; color: #1e293b; }
.osc-items { font-size: .7rem; color: #64748b; margin-top: .15rem;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
