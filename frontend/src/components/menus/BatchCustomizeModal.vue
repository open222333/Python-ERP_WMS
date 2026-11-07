<!-- [U10] 自 views/admin/MenusView.vue 拆出 -->
<script setup lang="ts">
// 品項批次設定客製化選項組（3 狀態：套用／移除／不改）
import { ref } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import type { MenuData } from './types'

const props = defineProps<{
  menuId:          string
  menu:            MenuData | null
  selectedItemIds: string[]
}>()
const emit = defineEmits<{ (e: 'saved'): void }>()

const toast = useToastStore()

const showBatchModal   = ref(false)
const batchSaving      = ref(false)
const batchGroupStates = ref<Record<string, 'add' | 'remove' | 'keep'>>({})

function open() {
  if (!props.selectedItemIds.length) {
    toast.show('請先勾選要批次編輯的品項', 'warning')
    return
  }
  const groups   = props.menu?.option_groups || []
  const selItems = (props.menu?.items || []).filter(i => props.selectedItemIds.includes(i._id))
  const states: Record<string, 'add' | 'remove' | 'keep'> = {}
  for (const og of groups) {
    const n = selItems.filter(i => i.applied_group_ids?.includes(og._id)).length
    states[og._id] = n === selItems.length ? 'add' : 'keep'
  }
  batchGroupStates.value = states
  showBatchModal.value   = true
}

function cycleBatchState(groupId: string) {
  const order: ('keep' | 'add' | 'remove')[] = ['keep', 'add', 'remove']
  const cur = batchGroupStates.value[groupId] || 'keep'
  batchGroupStates.value[groupId] = order[(order.indexOf(cur) + 1) % order.length]
}

async function saveBatch() {
  if (!props.menuId) return
  batchSaving.value = true
  const selItems = (props.menu?.items || []).filter(i => props.selectedItemIds.includes(i._id))
  try {
    await Promise.all(selItems.map(async item => {
      const ids = [...(item.applied_group_ids || [])]
      for (const [gid, state] of Object.entries(batchGroupStates.value)) {
        if (state === 'add' && !ids.includes(gid)) {
          ids.push(gid)
        } else if (state === 'remove') {
          const idx = ids.indexOf(gid)
          if (idx >= 0) ids.splice(idx, 1)
        }
      }
      const changed =
        JSON.stringify([...ids].sort()) !==
        JSON.stringify([...(item.applied_group_ids || [])].sort())
      if (changed) {
        await http.put(`/menu/${props.menuId}/item/${item._id}`, {
          ...item, applied_group_ids: ids,
        })
      }
    }))
    toast.show('批次更新完成', 'success')
    showBatchModal.value  = false
    emit('saved')   // 父層清空勾選並重新載入
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '批次更新失敗', 'danger')
  } finally {
    batchSaving.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <Teleport to="body">
    <!-- 批次客製化 Modal -->
    <div v-if="showBatchModal" class="modal fade show d-block bg-dim-50" @click.self="showBatchModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-sliders2 me-1 text-indigo"></i>批次設定客製化
            </h5>
            <button type="button" class="btn-close" @click="showBatchModal = false"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted small mb-3">
              已選 <strong>{{ selectedItemIds.length }}</strong> 個品項。點擊標籤循環切換狀態：
              <span class="batch-badge state-add">套用</span> 加入全部選中品項，
              <span class="batch-badge state-remove">移除</span> 從全部選中品項移除，
              <span class="batch-badge state-keep">不改</span> 保持各品項現有設定不變。
            </p>

            <div v-if="!menu?.option_groups?.length" class="text-muted fst-italic small">
              此菜單尚無客製化選項組，請至「客製化」tab 新增。
            </div>

            <div class="batch-group-list">
              <div v-for="og in menu?.option_groups" :key="og._id" class="batch-group-row">
                <div class="batch-group-info">
                  <div class="fw-semibold">{{ og.name }}</div>
                  <div class="text-muted small">
                    {{ og.type === 'single' ? '單選' : '多選' }} ·
                    {{ og.choices?.length || 0 }} 個選項
                    （{{ (og.choices || []).map(c => c.name).join('、') }}）
                  </div>
                </div>
                <button class="batch-state-btn"
                        :class="`state-${batchGroupStates[og._id] || 'keep'}`"
                        @click="cycleBatchState(og._id)">
                  {{ ({ add: '套用', remove: '移除', keep: '不改' } as Record<string,string>)[batchGroupStates[og._id] || 'keep'] }}
                </button>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showBatchModal = false">取消</button>
            <button class="btn btn-primary" :disabled="batchSaving" @click="saveBatch">
              <span v-if="batchSaving" class="spinner-border spinner-border-sm me-1"></span>
              儲存變更
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.text-indigo { color: #6366f1; }

.batch-group-list { display: flex; flex-direction: column; gap: 8px; }
/* [U13] 原寫死淺色底 #f8f9fb，深色模式下是一條白底；改用版面變數 */
.batch-group-row  {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; background: var(--table-th-bg, #f8f9fb); border-radius: 8px;
  border: 1px solid var(--card-border, #e8eaf0);
}
.batch-group-info { flex: 1; min-width: 0; }
.batch-state-btn  {
  padding: 5px 18px; border-radius: 20px; font-size: .82rem; font-weight: 700;
  border: 2px solid; cursor: pointer; transition: .15s; white-space: nowrap; flex-shrink: 0;
}
.batch-state-btn.state-keep   { background: #f1f5f9; border-color: #cbd5e1; color: #64748b; }
.batch-state-btn.state-add    { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.batch-state-btn.state-remove { background: #fee2e2; border-color: #fca5a5; color: #991b1b; }
.batch-state-btn:hover { filter: brightness(.92); }

.batch-badge {
  display: inline-block; padding: 1px 8px; border-radius: 20px;
  font-size: .75rem; font-weight: 600; border: 1.5px solid;
}
.batch-badge.state-keep   { background: #f1f5f9; border-color: #cbd5e1; color: #64748b; }
.batch-badge.state-add    { background: #d1fae5; border-color: #6ee7b7; color: #065f46; }
.batch-badge.state-remove { background: #fee2e2; border-color: #fca5a5; color: #991b1b; }
</style>
