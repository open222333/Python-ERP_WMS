<!-- [U10] 自 views/admin/SettingsView.vue 拆出 -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

export interface DiscountPreset { label: string; type: 'percent' | 'fixed'; value: number }

/** 初始值由 SettingsView 一次載入 /settings/ 後傳入，避免各區塊重複呼叫 */
const props = defineProps<{ initial: DiscountPreset[] }>()

const toast = useToastStore()
const discountPresets = ref<DiscountPreset[]>([])
const savingDisc      = ref(false)

watch(() => props.initial, v => { discountPresets.value = (v || []).map(p => ({ ...p })) }, { immediate: true })

function addDiscountRow() {
  discountPresets.value.push({ label: '', type: 'percent', value: 0 })
}

function removeDiscountRow(index: number) {
  discountPresets.value.splice(index, 1)
}

async function saveDiscountPresets() {
  const presets = discountPresets.value
    .filter(p => p.label.trim() && !isNaN(p.value) && (p.type === 'percent' ? p.value >= 0 : p.value > 0))
    .map(p => ({ label: p.label.trim(), type: p.type, value: Number(p.value) }))

  savingDisc.value = true
  try {
    await http.put('/settings/', { pos_discount_presets: presets })
    discountPresets.value = presets
    toast.show('折扣設定已儲存')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingDisc.value = false
  }
}
</script>

<template>
  <!-- ── POS 折扣快捷 ──────────────────────────────── -->
  <div class="col-12">
    <div class="table-card">
      <div class="table-header d-flex align-items-center justify-content-between">
        <h6><i class="bi bi-percent me-1 text-primary"></i>POS 折扣快捷</h6>
        <button class="btn btn-sm btn-outline-primary" @click="addDiscountRow">
          <i class="bi bi-plus-lg me-1"></i>新增
        </button>
      </div>
      <div class="p-3">
        <div class="row g-1 mb-2 align-items-center fz-72" style="color:#6b7280">
          <div class="col-3">顯示名稱</div>
          <div class="col-5">類型</div>
          <div class="col-2 text-end">數值</div>
          <div class="col-2"></div>
        </div>
        <div v-for="(p, i) in discountPresets" :key="i" class="row g-1 mb-1 align-items-center">
          <div class="col-3">
            <input
              v-model="p.label"
              type="text"
              class="form-control form-control-sm"
              placeholder="名稱"
            />
          </div>
          <div class="col-5">
            <select v-model="p.type" class="form-select form-select-sm">
              <option value="percent">折扣%（如 90 = 九折）</option>
              <option value="fixed">固定折抵（元）</option>
            </select>
          </div>
          <div class="col-2">
            <input
              v-model.number="p.value"
              type="number"
              class="form-control form-control-sm text-end"
              min="0"
              placeholder="數值"
            />
          </div>
          <div class="col-2 text-end">
            <button
              type="button"
              class="btn btn-sm btn-outline-danger py-0 px-1"
              @click="removeDiscountRow(i)"
             aria-label="移除" title="移除">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
        <div class="form-text mb-3 mt-2">
          <b>折扣%</b>：輸入數字，例如 90 = 九折（小計 × 0.9）。填 <b>0</b> = 免費贈送（全額折抵）。<br />
          <b>固定折抵</b>：輸入折抵金額，例如 50 = 折抵 $50。
        </div>
        <button class="btn btn-primary" :disabled="savingDisc" @click="saveDiscountPresets">
          <span v-if="savingDisc" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-save me-1"></i>儲存折扣設定
        </button>
      </div>
    </div>
  </div>
</template>
