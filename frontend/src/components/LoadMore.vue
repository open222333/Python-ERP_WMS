<script setup lang="ts">
/**
 * [U3] 列表底部「載入更多」：原本列表只拿後端預設筆數（如 POS 銷售 50 筆）且沒有任何提示。
 * 搭配頁面的 load(append) 使用：hasMore = 這一批筆數 === PAGE_SIZE。
 */
defineProps<{ count: number; hasMore: boolean; loading?: boolean }>()
defineEmits<{ (e: 'more'): void }>()
</script>

<template>
  <div v-if="count" class="load-more d-flex align-items-center justify-content-between gap-2 px-3 py-2 border-top">
    <span class="text-muted small">已顯示 {{ count }} 筆{{ hasMore ? '' : '（全部）' }}</span>
    <button v-if="hasMore" class="btn btn-sm btn-outline-primary" :disabled="loading" @click="$emit('more')">
      <span v-if="loading" class="spinner-border spinner-border-sm me-1"></span>
      載入更多
    </button>
  </div>
</template>
