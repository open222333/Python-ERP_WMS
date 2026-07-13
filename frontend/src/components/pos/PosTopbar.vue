<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <div id="topbar">
    <div class="tb-logo"><i class="bi bi-cash-register"></i>POS 收銀</div>
    <div class="tb-sep"></div>
    <select v-model="warehouseModel" class="form-select" style="width:150px">
      <option value="">全部倉庫</option>
      <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
    </select>
    <select v-model="menuModel" class="form-select" style="width:160px">
      <option value="" disabled>-- 選擇菜單 --</option>
      <option v-for="m in menus" :key="m._id" :value="m._id">{{ m.name }}</option>
    </select>
    <div id="scan-bar">
      <i class="bi bi-upc-scan scan-icon"></i>
      <input v-model="scanInput" type="text" placeholder="掃描條碼…"
             autocomplete="off" @keydown.enter="onScan" ref="scanRef" />
    </div>
    <div style="flex:1"></div>
    <span id="topbar-clock">{{ clock }}</span>
    <div class="tb-sep"></div>
    <span id="topbar-user">👤 {{ auth.username }}</span>
    <button class="tb-btn tb-btn-history" @click="emit('show-history')">
      <i class="bi bi-clock-history"></i>銷售記錄
    </button>
    <button class="tb-btn danger" @click="handleLogout">
      <i class="bi bi-box-arrow-right"></i>登出
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const props = defineProps<{
  warehouse:  string
  menu:       string
  warehouses: any[]
  menus:      any[]
  products:   any[]
}>()

const emit = defineEmits<{
  (e: 'update:warehouse', v: string): void
  (e: 'update:menu', v: string): void
  (e: 'show-history'): void
  (e: 'add-product', p: any): void
}>()

const auth   = useAuthStore()
const toast  = useToastStore()
const router = useRouter()

const warehouseModel = computed({
  get: () => props.warehouse,
  set: v => emit('update:warehouse', v),
})
const menuModel = computed({
  get: () => props.menu,
  set: v => emit('update:menu', v),
})

const scanInput = ref('')
const scanRef   = ref<HTMLInputElement>()

const clock = ref('')
let clockTimer: ReturnType<typeof setInterval>

function tickClock() {
  clock.value = new Date().toLocaleTimeString('zh-TW', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function onScan() {
  const sku = scanInput.value.trim()
  if (!sku) return
  const p = props.products.find((p: any) => p.sku === sku)
  if (p) { emit('add-product', p); scanInput.value = '' }
  else toast.show(`找不到條碼：${sku}`, 'danger')
}

async function handleLogout() {
  auth.logout()
  await router.push('/login')
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  setTimeout(() => scanRef.value?.focus(), 300)
})
onUnmounted(() => clearInterval(clockTimer))
</script>

<style scoped>
/* Topbar */
#topbar {
  height: var(--topbar-h);
  background: #1e2235;
  display: flex; align-items: center; gap: 12px;
  padding: 0 16px; flex-shrink: 0; color: #fff;
}
.tb-logo { font-weight: 700; font-size: 1rem; letter-spacing: .5px;
           white-space: nowrap; display: flex; align-items: center; gap: 6px; }
.tb-logo i { color: #7c9cff; font-size: 1.2rem; }
#topbar .form-select { background: #2c3148; border-color: #3d4566; color: #e2e8f0; font-size: .82rem; }
#scan-bar { flex: 0 0 220px; position: relative; }
#scan-bar input { background: #2c3148; border: 1px solid #3d4566; color: #e2e8f0;
                  border-radius: 8px; padding: 5px 10px 5px 32px; width: 100%; font-size: .82rem; }
#scan-bar input:focus { outline: none; border-color: var(--accent); }
.scan-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #6b7280; pointer-events: none; }
#topbar-clock, #topbar-user { font-size: .82rem; color: #94a3b8; white-space: nowrap; }
.tb-btn { background: #2c3148; border: 1px solid #3d4566; color: #cbd5e1;
          border-radius: 7px; padding: 5px 10px; font-size: .78rem; cursor: pointer;
          display: flex; align-items: center; gap: 5px; white-space: nowrap; transition: background .15s; }
.tb-btn:hover { background: #3a4060; }
.tb-btn.danger { border-color: #7f1d1d; color: #fca5a5; }
.tb-btn.danger:hover { background: #7f1d1d; }
.tb-btn.tb-btn-history {
  padding: 10px 20px;
  font-size: 1.56rem;
  border-radius: 14px;
  gap: 10px;
}
.tb-sep { width: 1px; height: 24px; background: #3d4566; flex-shrink: 0; }
</style>
