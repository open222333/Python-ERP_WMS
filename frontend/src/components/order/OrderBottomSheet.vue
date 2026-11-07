<!-- [U10] 自 views/OrderView.vue 拆出 -->
<script setup lang="ts">
// 手機底部抽屜外框（購物車、客製化共用）；內容由 slot 提供
defineProps<{ show: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="bottom-mask" @click.self="emit('close')">
      <div class="bottom-sheet" role="dialog" aria-modal="true">
        <div class="bs-header">
          <slot name="header" />
          <button class="btn-close" aria-label="關閉" @click="emit('close')"></button>
        </div>
        <div class="bs-body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="bs-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Bottom Sheet（購物車 drawer + 客製化 modal） ── */
.bottom-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.5);
  z-index: 1050;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.bottom-sheet {
  background: #fff;
  border-radius: 16px 16px 0 0;
  width: 100%;
  max-width: 480px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
}
.bs-header {
  padding: 1rem 1rem .75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.bs-body {
  padding: .75rem 1rem;
  overflow-y: auto;
  flex: 1;
}
.bs-footer {
  padding: .75rem 1rem;
  padding-bottom: calc(.75rem + env(safe-area-inset-bottom));   /* [MOBILE] */
  border-top: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: .75rem;
  flex-shrink: 0;
}
</style>
