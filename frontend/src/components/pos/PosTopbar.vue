<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <div id="topbar">
    <div class="tb-logo"><i class="bi bi-cash-register"></i>POS 收銀</div>
    <div class="tb-sep"></div>
    <select v-model="warehouseModel" class="form-select tb-select-wh" aria-label="倉庫">
      <option value="">全部倉庫</option>
      <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
    </select>
    <select v-model="menuModel" class="form-select tb-select-menu" aria-label="菜單">
      <option value="" disabled>-- 選擇菜單 --</option>
      <option v-for="m in menus" :key="m._id" :value="m._id">{{ m.name }}</option>
    </select>
    <div id="scan-bar">
      <i class="bi bi-upc-scan scan-icon"></i>
      <input v-model="scanInput" type="text" placeholder="掃描條碼…"
             autocomplete="off" @keydown.enter="onScan" ref="scanRef" />
    </div>
    <div class="tb-spacer"></div>
    <span id="topbar-clock">{{ clock }}</span>
    <div class="tb-sep tb-sep-user"></div>
    <span id="topbar-user">👤 {{ auth.username }}</span>
    <button class="tb-btn tb-btn-history" @click="emit('show-history')" aria-label="銷售記錄" title="銷售記錄">
      <i class="bi bi-clock-history"></i><span class="tb-btn-text">銷售記錄</span>
    </button>
    <button class="tb-btn danger" @click="handleLogout" aria-label="登出" title="登出">
      <i class="bi bi-box-arrow-right"></i><span class="tb-btn-text">登出</span>
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
/* [U13] 原本 1.56rem＋10px 內距，按鈕高於頂列（52px）而溢出；維持醒目但收在頂列內 */
.tb-btn.tb-btn-history {
  padding: 6px 16px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 10px;
  gap: 8px;
  max-height: calc(var(--topbar-h, 52px) - 10px);
}
.tb-sep { width: 1px; height: 24px; background: #3d4566; flex-shrink: 0; }
.tb-spacer { flex: 1; }
.tb-select-wh   { width: 150px; }
.tb-select-menu { width: 160px; }

/* [U13] 手機橫向／小平板（實測 844px 寬時右側的銷售記錄、登出按鈕被擠出畫面）：
   隱藏時鐘與使用者、縮窄選單，按鈕只留圖示 */
@media (max-width: 1023.98px) {
  #topbar { gap: 8px; padding: 0 10px; }
  #topbar-clock, #topbar-user, .tb-sep-user { display: none; }
  .tb-select-wh, .tb-select-menu { width: 120px; flex-shrink: 1; min-width: 90px; }
  #scan-bar { flex: 1 1 140px; min-width: 110px; }
  .tb-spacer { display: none; }
}
@media (max-width: 899.98px) {
  .tb-logo { font-size: .9rem; }
  .tb-btn .tb-btn-text { display: none; }
  .tb-btn, .tb-btn.tb-btn-history { padding: 6px 10px; font-size: 1.05rem; }
}
</style>
