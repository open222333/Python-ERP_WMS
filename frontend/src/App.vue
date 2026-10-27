<template>
  <RouterView />
  <AppConfirm />
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppConfirm from '@/components/AppConfirm.vue'   // [U5] 全站共用確認框
</script>
