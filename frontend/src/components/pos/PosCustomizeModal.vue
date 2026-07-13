<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- ── 客製化選項 Modal ─────────────────────────── -->
  <Teleport to="body">
    <div class="modal-backdrop-custom" @click.self="emit('close')">
      <div class="modal-box-custom">
        <div class="modal-header">
          <div>
            <h5 class="modal-title"><i class="bi bi-sliders2 me-1"></i>{{ target?.name }}</h5>
            <div class="text-muted small mt-1">NT$ {{ target?.price }}</div>
          </div>
          <button class="btn-close" @click="emit('close')"></button>
        </div>
        <div class="modal-body" style="max-height:60vh;overflow-y:auto">
          <div v-for="grp in target?.applied_groups" :key="grp._id" class="og-section">
            <div class="og-title">
              {{ grp.name }}
              <span v-if="grp.required" class="og-badge required">必選</span>
              <span v-if="grp.type === 'multiple'" class="og-badge multi">可複選</span>
            </div>
            <!-- Single: radio pill -->
            <div class="og-choices">
              <label v-for="ch in grp.choices" :key="ch._id"
                     class="choice-pill"
                     :class="{ active: customSelections[grp._id]?.includes(ch._id) }">
                <input v-if="grp.type === 'single'" type="radio"
                       :name="`grp-${grp._id}`"
                       :checked="customSelections[grp._id]?.[0] === ch._id"
                       @change="customSelections[grp._id] = [ch._id]"
                       style="display:none" />
                <input v-else type="checkbox"
                       :checked="customSelections[grp._id]?.includes(ch._id)"
                       @change="toggleMultiChoice(grp._id, ch._id)"
                       style="display:none" />
                {{ ch.name }}
                <span v-if="ch.extra_price > 0" class="choice-extra">+{{ ch.extra_price }}</span>
              </label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="emit('close')">取消</button>
          <button class="btn btn-primary fw-bold px-4" @click="confirmCustom">
            <i :class="isEdit ? 'bi bi-check-lg' : 'bi bi-cart-plus'" class="me-1"></i>
            {{ isEdit ? '確認修改' : '加入購物車' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useToastStore } from '@/stores/toast'
import type { SelectionItem } from './types'

const props = defineProps<{
  target:            any
  initialSelections: Record<string, string[]>
  isEdit:            boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', selections: SelectionItem[]): void
}>()

const toast = useToastStore()

const customSelections = ref<Record<string, string[]>>({ ...props.initialSelections })

function toggleMultiChoice(groupId: string, choiceId: string) {
  const arr = customSelections.value[groupId] || []
  const i = arr.indexOf(choiceId)
  customSelections.value[groupId] = i >= 0
    ? arr.filter(id => id !== choiceId)
    : [...arr, choiceId]
}

function confirmCustom() {
  const groups: any[] = props.target?.applied_groups || []
  // 驗證必選
  for (const grp of groups) {
    if (grp.required && !(customSelections.value[grp._id]?.length)) {
      toast.show(`請選擇「${grp.name}」`, 'danger')
      return
    }
  }
  // 建立選擇陣列
  const selections: SelectionItem[] = []
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const choice = (grp.choices || []).find((c: any) => c._id === cid)
      if (choice) {
        selections.push({
          group_id:    grp._id,
          group_name:  grp.name,
          choice_id:   cid,
          choice_name: choice.name,
          extra_price: choice.extra_price || 0,
        })
      }
    }
  }
  emit('confirm', selections)
}
</script>

<style scoped>
/* Modal backdrop（複製自 PosView.vue 共用樣式） */
.modal-backdrop-custom { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1050; display: flex; align-items: center; justify-content: center; overflow-y: auto; padding: 16px; }

/* 客製化 Modal */
.modal-box-custom {
  background: #fff; border-radius: 14px;
  width: 460px; max-width: 95vw;
  box-shadow: 0 20px 60px rgba(0,0,0,.3);
}
.og-section { margin-bottom: 20px; }
.og-title {
  font-size: .88rem; font-weight: 700; color: #1e2235;
  margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.og-badge {
  font-size: .65rem; font-weight: 700; padding: 2px 7px; border-radius: 20px;
}
.og-badge.required { background: #fee2e2; color: #dc2626; }
.og-badge.multi    { background: #e0e7ff; color: #4f46e5; }
.og-choices { display: flex; flex-wrap: wrap; gap: 8px; }
.choice-pill {
  padding: 6px 14px; border-radius: 20px; font-size: .82rem; font-weight: 600;
  border: 2px solid #e2e8f0; background: #f8f9fb; color: #374151;
  cursor: pointer; transition: all .15s; user-select: none;
  display: flex; align-items: center; gap: 4px;
}
.choice-pill:hover { border-color: var(--accent); color: var(--accent); }
.choice-pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.choice-extra { font-size: .72rem; opacity: .85; }

.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #e9ecef; }
.modal-title  { font-size: 1rem; font-weight: 600; margin: 0; }
.modal-body   { padding: 18px; }
.modal-footer { padding: 12px 18px; border-top: 1px solid #e9ecef; display: flex; gap: 8px; justify-content: flex-end; }
</style>
