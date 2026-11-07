<!-- [U10] 自 views/admin/MenusView.vue 拆出 -->
<script setup lang="ts">
// 客製化選項組新增／編輯彈窗（常駐元件，草稿行為同品項彈窗）
import { ref } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { useFieldErrors } from '@/composables/useFieldErrors'
import type { OptionGroup } from './types'

const props = defineProps<{ menuId: string }>()
const emit  = defineEmits<{ (e: 'saved'): void }>()

const toast = useToastStore()
const fe    = useFieldErrors()   // [U9]

// 選項組表單
const showOgModal = ref(false)
const ogSaving    = ref(false)
const ogForm = ref<{
  _id: string
  name: string
  type: 'single' | 'multiple'
  required: boolean
  choices: { _id: string; name: string; extra_price: number; is_default: boolean }[]
}>({
  _id: '', name: '', type: 'single', required: true, choices: [],
})

function open(og?: OptionGroup) {
  fe.clear()
  if (og) {
    ogForm.value = {
      _id:      og._id,
      name:     og.name,
      type:     og.type,
      required: og.required,
      choices:  og.choices.map(c => ({ ...c })),
    }
  } else if (ogForm.value._id) {
    ogForm.value = { _id: '', name: '', type: 'single', required: true, choices: [] }
  }
  showOgModal.value = true
}

function addChoice() {
  ogForm.value.choices.push({ _id: '', name: '', extra_price: 0, is_default: false })
}

function removeChoice(idx: number) {
  ogForm.value.choices.splice(idx, 1)
}

function setDefault(idx: number) {
  if (ogForm.value.type === 'single') {
    // 單選：只能一個預設
    ogForm.value.choices.forEach((c, i) => { c.is_default = i === idx })
  } else {
    ogForm.value.choices[idx].is_default = !ogForm.value.choices[idx].is_default
  }
}

async function saveOg() {
  if (!fe.check({ og_name: [!ogForm.value.name.trim(), '請填寫選項組名稱'] })) return
  if (!props.menuId) return
  ogSaving.value = true
  const isNew = !ogForm.value._id
  try {
    const payload = {
      name:     ogForm.value.name.trim(),
      type:     ogForm.value.type,
      required: ogForm.value.required,
      choices:  ogForm.value.choices
        .map(c => ({
          name:        c.name.trim(),
          extra_price: Number(c.extra_price) || 0,
          is_default:  c.is_default,
        }))
        .filter(c => c.name),
    }
    if (ogForm.value._id) {
      await http.put(`/menu/${props.menuId}/option-group/${ogForm.value._id}`, payload)
    } else {
      await http.post(`/menu/${props.menuId}/option-group`, payload)
    }
    toast.show('儲存成功', 'success')
    showOgModal.value = false
    if (isNew) ogForm.value = { _id: '', name: '', type: 'single', required: true, choices: [] }
    emit('saved')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    ogSaving.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <Teleport to="body">
    <!-- 選項組 Modal -->
    <div v-if="showOgModal" class="modal fade show d-block bg-dim-50" @click.self="showOgModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-sliders2 me-1"></i>{{ ogForm._id ? '編輯選項組' : '新增選項組' }}
            </h5>
            <button type="button" class="btn-close" @click="showOgModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3 mb-3">
              <div class="col-md-5">
                <label class="form-label fw-semibold">選項組名稱 <span class="text-danger">*</span></label>
                <input v-model="ogForm.name" type="text" class="form-control" placeholder="例：辣度、甜度"
                     data-field="og_name" :class="{ 'is-invalid': fe.errors.og_name }"
                     @input="fe.clear('og_name')" />
              <div class="invalid-feedback">{{ fe.errors.og_name }}</div>
              </div>
              <div class="col-md-4">
                <label class="form-label fw-semibold">選擇類型</label>
                <select v-model="ogForm.type" class="form-select">
                  <option value="single">單選（只能選一個）</option>
                  <option value="multiple">多選（可選多個）</option>
                </select>
              </div>
              <div class="col-md-3 d-flex align-items-end">
                <div class="form-check form-switch mb-0 pb-2">
                  <input v-model="ogForm.required" class="form-check-input" type="checkbox" id="og-required" />
                  <label class="form-check-label fw-semibold" for="og-required">必選</label>
                </div>
              </div>
            </div>

            <!-- 選項清單 -->
            <div class="d-flex align-items-center justify-content-between mb-2">
              <label class="form-label fw-semibold mb-0">選項清單</label>
              <button class="btn btn-sm btn-outline-primary" type="button" @click="addChoice">
                <i class="bi bi-plus-lg"></i> 新增選項
              </button>
            </div>
            <div v-if="!ogForm.choices.length" class="text-muted small fst-italic mb-2">
              尚無選項，點右上角新增
            </div>
            <div class="og-choice-list">
              <div v-for="(ch, idx) in ogForm.choices" :key="idx" class="og-choice-row">
                <div class="flex-grow-1">
                  <input v-model="ch.name" type="text" class="form-control form-control-sm"
                         placeholder="選項名稱（例：不辣）" />
                </div>
                <div class="wpx-110">
                  <div class="input-group input-group-sm">
                    <span class="input-group-text">+$</span>
                    <input v-model.number="ch.extra_price" type="number" class="form-control" min="0" step="1" placeholder="0" />
                  </div>
                </div>
                <div>
                  <button type="button"
                    class="btn btn-sm"
                    :class="ch.is_default ? 'btn-warning' : 'btn-outline-secondary'"
                    @click="setDefault(idx)"
                    :title="ogForm.type === 'single' ? '設為預設' : '切換預設'">
                    <i class="bi" :class="ch.is_default ? 'bi-star-fill' : 'bi-star'"></i>
                  </button>
                </div>
                <div>
                  <button type="button" class="btn btn-sm btn-outline-danger" @click="removeChoice(idx)" aria-label="移除" title="移除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="form-text mt-1">
              <i class="bi bi-star-fill text-warning me-1"></i>金色星號 = POS 預設勾選；加價 0 = 不另加收費
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showOgModal = false">取消</button>
            <button class="btn btn-primary" :disabled="ogSaving" @click="saveOg">
              <span v-if="ogSaving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 選項組 Modal 選項列 */
.og-choice-list { display: flex; flex-direction: column; gap: 8px; }
.og-choice-row  { display: flex; align-items: center; gap: 8px; }
</style>
