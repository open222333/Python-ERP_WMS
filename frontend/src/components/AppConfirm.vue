<script setup lang="ts">
/** [U5] 全站共用確認框（由 composables/useConfirm.ts 的 appConfirm／appAlert 開啟） */
import { ref, watch, nextTick } from 'vue'
import { dialogState, closeDialog } from '@/composables/useConfirm'

const okBtn = ref<HTMLButtonElement | null>(null)

// 開啟時把焦點移到確定鈕，Enter 即確認、Esc 即取消（Esc 由 modal 增強器統一處理）
watch(() => dialogState.open, async (v) => {
  if (v) { await nextTick(); okBtn.value?.focus() }
})
</script>

<template>
  <Teleport to="body">
    <div v-if="dialogState.open" class="modal d-block app-confirm" role="dialog" aria-modal="true"
         :aria-label="dialogState.title" style="background:rgba(0,0,0,.45);z-index:10050"
         @click.self="closeDialog(false)">
      <div class="modal-dialog modal-dialog-centered modal-sm">
        <div class="modal-content">
          <div class="modal-header py-2">
            <h6 class="modal-title fw-bold">{{ dialogState.title }}</h6>
            <button type="button" class="btn-close" aria-label="關閉" @click="closeDialog(false)"></button>
          </div>
          <div class="modal-body" style="white-space:pre-line">{{ dialogState.message }}</div>
          <div class="modal-footer py-2">
            <button v-if="!dialogState.alertOnly" type="button" class="btn btn-secondary"
                    @click="closeDialog(false)">{{ dialogState.cancelText }}</button>
            <button ref="okBtn" type="button" class="btn"
                    :class="dialogState.danger ? 'btn-danger' : 'btn-primary'"
                    @click="closeDialog(true)">{{ dialogState.okText }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.app-confirm .modal-dialog { max-width: min(380px, 92vw); margin-left: auto; margin-right: auto; }
</style>
