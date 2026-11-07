<!-- [U10] 自 views/OrderView.vue 拆出 -->
<script setup lang="ts">
// 品項客製化選擇（底部抽屜）。open(item) 開啟並預選預設選項，確認後 emit('add')
import { ref, computed } from 'vue'
import { appAlert } from '@/composables/useConfirm'
import OrderBottomSheet from './OrderBottomSheet.vue'
import type { SelectionItem } from './orderCart'

const emit = defineEmits<{ (e: 'add', item: any, selections: SelectionItem[], qty: number): void }>()

const showCustomModal  = ref(false)
const customTarget     = ref<any>(null)
const customSelections = ref<Record<string, string[]>>({})
const custQty          = ref(1)

const custTotalPrice = computed(() => {
  if (!customTarget.value) return 0
  const groups: any[] = customTarget.value.applied_groups || []
  let extra = 0
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const ch = (grp.choices || []).find((c: any) => c._id === cid)
      if (ch) extra += ch.extra_price || 0
    }
  }
  return (customTarget.value.price + extra) * custQty.value
})

function open(item: any) {
  const groups: any[] = item.applied_groups || []
  {
    custQty.value      = 1
    customTarget.value = item
    // 初始化：預選 is_default
    const sel: Record<string, string[]> = {}
    for (const grp of groups) {
      if (grp.type === 'single') {
        const def = (grp.choices || []).find((c: any) => c.is_default)
        sel[grp._id] = def ? [def._id] : []
      } else {
        sel[grp._id] = (grp.choices || []).filter((c: any) => c.is_default).map((c: any) => c._id)
      }
    }
    customSelections.value = sel
    showCustomModal.value  = true
  }
}

function toggleMultiChoice(groupId: string, choiceId: string) {
  const arr = customSelections.value[groupId] || []
  const i   = arr.indexOf(choiceId)
  customSelections.value[groupId] = i >= 0
    ? arr.filter(id => id !== choiceId)
    : [...arr, choiceId]
}

function confirmCustom() {
  const groups: any[] = customTarget.value?.applied_groups || []
  for (const grp of groups) {
    if (grp.required && !(customSelections.value[grp._id]?.length)) {
      appAlert(`請選擇「${grp.name}」`)
      return
    }
  }
  const selections: SelectionItem[] = []
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const ch = (grp.choices || []).find((c: any) => c._id === cid)
      if (ch) {
        selections.push({
          group_id:    grp._id,
          group_name:  grp.name,
          choice_id:   cid,
          choice_name: ch.name,
          extra_price: ch.extra_price || 0,
        })
      }
    }
  }
  emit('add', customTarget.value, selections, custQty.value)
  showCustomModal.value = false
}

defineExpose({ open })
</script>

<template>
  <OrderBottomSheet :show="showCustomModal" @close="showCustomModal = false">
    <template #header>
      <div>
        <div class="fw-bold">{{ customTarget?.name }}</div>
        <div class="text-primary small">NT${{ customTarget?.price }}</div>
      </div>
    </template>

    <template v-if="customTarget">
      <div v-for="grp in customTarget.applied_groups" :key="grp._id" class="og-section">
        <div class="og-title">
          {{ grp.name }}
          <span v-if="grp.required" class="badge bg-danger ms-1 og-badge">必選</span>
          <span v-if="grp.type === 'multiple'" class="badge bg-secondary ms-1 og-badge">可複選</span>
        </div>
        <div class="og-choices">
          <div v-for="ch in grp.choices" :key="ch._id"
               class="choice-pill"
               :class="{ active: customSelections[grp._id]?.includes(ch._id) }"
               role="button" tabindex="0"
               @keydown.enter.prevent="($event.currentTarget as HTMLElement).click()"
               @click="grp.type === 'single'
                         ? (customSelections[grp._id] = [ch._id])
                         : toggleMultiChoice(grp._id, ch._id)">
            {{ ch.name }}
            <span v-if="ch.extra_price > 0" class="choice-extra">+{{ ch.extra_price }}</span>
          </div>
        </div>
      </div>
      <div v-if="!customTarget.applied_groups?.length"
           class="text-center text-muted small py-3">無客製選項</div>
    </template>

    <template #footer>
      <div class="qty-ctrl">
        <button aria-label="減少數量" @click="custQty > 1 && custQty--">－</button>
        <span>{{ custQty }}</span>
        <button aria-label="增加數量" @click="custQty++">＋</button>
      </div>
      <div class="cust-total-lbl">NT${{ custTotalPrice }}</div>
      <button class="btn btn-primary fw-semibold px-3" @click="confirmCustom">
        <i class="bi bi-cart-plus me-1"></i>加入
      </button>
    </template>
  </OrderBottomSheet>
</template>

<style scoped>
/* ── 客製化選項 ────────────────────────────────── */
.og-section   { margin-bottom: 1.1rem; }
.og-title     { font-weight: 700; font-size: .88rem; margin-bottom: .5rem; }
.og-badge     { font-size: .6rem !important; }
.og-choices   { display: flex; flex-wrap: wrap; gap: .4rem; }
.choice-pill  {
  padding: .35rem .8rem;
  border-radius: 20px;
  border: 1.5px solid #e2e8f0;
  font-size: .82rem;
  cursor: pointer;
  user-select: none;
  transition: all .15s;
  background: #f8fafc;
}
.choice-pill.active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.choice-extra { font-size: .7rem; color: #3b82f6; margin-left: .2rem; }

.qty-ctrl { display: flex; align-items: center; gap: .35rem; }
.qty-ctrl button {
  width: 2rem; height: 2rem;
  border: 1.5px solid #e2e8f0; border-radius: 8px;
  background: #f8fafc; font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.qty-ctrl span { font-size: 1rem; font-weight: 700; min-width: 1.5rem; text-align: center; }
.cust-total-lbl { flex: 1; text-align: right; font-weight: 700; font-size: 1rem; color: #3b82f6; }
</style>
