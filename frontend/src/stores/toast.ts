import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastVariant = 'success' | 'danger' | 'warning' | 'info'

export interface ToastItem {
  id:      number
  message: string
  variant: ToastVariant
}

let _id = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<ToastItem[]>([])

  function show(message: string, variant: ToastVariant = 'success', duration = 3000) {
    const id = ++_id
    toasts.value.push({ id, message, variant })
    setTimeout(() => remove(id), duration)
  }

  function remove(id: number) {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  return { toasts, show, remove }
})
