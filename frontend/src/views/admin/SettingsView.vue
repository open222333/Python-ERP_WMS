<script setup lang="ts">
// [U10] 2026-11 拆分：折扣快捷、付款方式、操作紀錄、外觀配色移至 components/settings/，
//        本頁只保留倉庫／POS 預設值，並統一載入一次 /settings/ 分給各區塊
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import DiscountPresetsSettings, { type DiscountPreset } from '@/components/settings/DiscountPresetsSettings.vue'
import PayMethodsSettings from '@/components/settings/PayMethodsSettings.vue'
import LogRetentionSettings from '@/components/settings/LogRetentionSettings.vue'
import AppearanceSettings from '@/components/settings/AppearanceSettings.vue'

const toast = useToastStore()
const authStore = useAuthStore()

// ── Types ────────────────────────────────────────────────
interface Warehouse { _id: string; name: string; code?: string }
interface Store    { _id: string; name: string }
interface Menu { _id: string; name: string }

// ── State ────────────────────────────────────────────────
const loading    = ref(false)
const saving     = ref(false)
const savingPos  = ref(false)

const warehouses         = ref<Warehouse[]>([])
const stores             = ref<Store[]>([])
const menus              = ref<Menu[]>([])
const defaultWarehouseId = ref('')
const posDefaultMenuId   = ref('')
const posDefaultStoreId  = ref('')

/** /settings/ 原始內容，分給子元件（外觀、折扣、紀錄保留）初始化 */
const settings           = ref<Record<string, any> | null>(null)
const discountPresets    = ref<DiscountPreset[]>([])
const logRetentionDays   = ref(0)
const logLastCleanup     = ref<string | null>(null)

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [whR, settR, menR, stR] = await Promise.all([
      http.get('/warehouse/'),
      http.get('/settings/'),
      http.get('/menu/?status=1'),
      http.get('/store/').catch(() => ({ data: { data: [] } })),
    ])

    warehouses.value         = whR.data?.data || []
    stores.value             = stR.data?.data || []
    menus.value              = menR.data?.data || []
    const s                  = settR.data?.data || {}
    settings.value           = s
    defaultWarehouseId.value = s.default_warehouse_id  || ''
    posDefaultMenuId.value   = s.pos_default_menu_id   || ''
    posDefaultStoreId.value  = s.pos_default_store_id  || ''
    logRetentionDays.value   = Number(s.log_retention_days ?? 0)
    logLastCleanup.value     = s.log_last_cleanup_at   || null
    discountPresets.value    = s.pos_discount_presets  || []
  } catch {
    toast.show('載入設定失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Save warehouse + POS default menu ────────────────────
async function saveSettings() {
  saving.value = true
  try {
    await http.put('/settings/', {
      default_warehouse_id: defaultWarehouseId.value || null,
    })
    toast.show('倉庫設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function savePosSettings() {
  savingPos.value = true
  try {
    await http.put('/settings/', {
      pos_default_menu_id:  posDefaultMenuId.value  || null,
      pos_default_store_id: posDefaultStoreId.value || null,
    })
    // 同步更新 auth store 的作業店家
    if (posDefaultStoreId.value) {
      authStore.activeStoreId = posDefaultStoreId.value
    }
    toast.show('POS 設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingPos.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="row g-4">

    <!-- ── 倉庫設定 ───────────────────────────────────── -->
    <div class="col-12 col-xl-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-building me-1 text-primary"></i>倉庫設定</h6>
        </div>
        <div class="p-4">
          <div class="mb-4">
            <label class="form-label fw-semibold">預設倉庫</label>
            <select v-model="defaultWarehouseId" class="form-select">
              <option value="">— 不指定預設倉庫 —</option>
              <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
            </select>
            <div class="form-text mt-2">
              <span class="badge bg-primary me-1">POS 收銀台</span>
              <span class="badge bg-warning text-dark me-1">快速出入庫</span>
              開啟時自動選取此倉庫，減少每次手動選擇。
            </div>
          </div>
          <button class="btn btn-primary" :disabled="saving" @click="saveSettings">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-save me-1"></i>儲存設定
          </button>
        </div>
      </div>
    </div>

    <!-- ── POS 預設菜單 ──────────────────────────────── -->
    <div class="col-12 col-xl-6">
      <div class="table-card">
        <div class="table-header">
          <h6><i class="bi bi-menu-button-wide me-1 text-primary"></i>POS 收銀台設定</h6>
        </div>
        <div class="p-4">
          <div class="mb-4">
            <label class="form-label fw-semibold">預設菜單</label>
            <select v-model="posDefaultMenuId" class="form-select">
              <option value="">— 不指定預設菜單（顯示全部商品）—</option>
              <option v-for="m in menus" :key="m._id" :value="m._id">{{ m.name }}</option>
            </select>
            <div class="form-text mt-2">
              <span class="badge bg-primary me-1">POS 收銀台</span>
              開啟時自動切換至此菜單，仍可手動切換至其他菜單或商品模式。
            </div>
          </div>
          <div class="mb-4">
            <label class="form-label fw-semibold">預設綁定店家</label>
            <select v-model="posDefaultStoreId" class="form-select">
              <option value="">— 不指定（依登入帳號的所屬店家）—</option>
              <option v-for="s in stores" :key="s._id" :value="s._id">{{ s.name }}</option>
            </select>
            <div class="form-text mt-2">
              <span class="badge bg-primary me-1">POS 收銀台</span>
              銷售紀錄自動歸屬至此店家。若登入帳號已有所屬店家，以帳號設定為優先。
            </div>
          </div>
          <button class="btn btn-primary" :disabled="savingPos" @click="savePosSettings">
            <span v-if="savingPos" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-save me-1"></i>儲存設定
          </button>
        </div>
      </div>
    </div>

    <!-- 設定用途說明已移至使用說明文件 -->
    <div class="col-12 col-xl-6 d-flex align-items-start">
      <a href="/docs/#settings" target="_blank"
         class="d-inline-flex align-items-center gap-2 text-primary text-decoration-none small mt-1">
        <i class="bi bi-book"></i>
        各設定項目的詳細說明請參閱使用說明文件 →
      </a>
    </div>

    <DiscountPresetsSettings :initial="discountPresets" />
    <PayMethodsSettings />
    <LogRetentionSettings :initial-days="logRetentionDays" :initial-last-cleanup="logLastCleanup" />
    <AppearanceSettings :settings="settings" />

  </div>
</template>
