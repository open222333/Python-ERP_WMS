<template>
  <Teleport to="body">
    <div class="toast-container position-fixed top-0 end-0 p-3" style="z-index:9999">
      <div
        v-for="t in toastStore.toasts"
        :key="t.id"
        class="toast show align-items-center"
        :class="`text-bg-${t.variant} border-0`"
        role="alert"
        aria-live="assertive"
      >
        <div class="d-flex">
          <div class="toast-body">{{ t.message }}</div>
          <button
            type="button"
            class="btn-close btn-close-white me-2 m-auto"
            @click="toastStore.remove(t.id)"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useToastStore } from '@/stores/toast'
const toastStore = useToastStore()
</script>
