/**
 * [U9] 表單欄位層級錯誤提示
 *
 *   const fe = useFieldErrors()
 *   if (!fe.check({ name: [!form.name.trim(), '請填寫名稱'] })) return
 *   <input :class="{ 'is-invalid': fe.errors.name }" @input="fe.clear('name')" />
 *   <div class="invalid-feedback">{{ fe.errors.name }}</div>
 *
 * 錯誤留在欄位旁直到使用者修改，不像 toast 3 秒就消失。
 * 後端錯誤目前只回 message、不帶欄位名，需要時用 fe.set('sku', msg) 手動對應。
 */
import { reactive } from 'vue'

export function useFieldErrors() {
  const errors = reactive<Record<string, string>>({})

  function clear(field?: string) {
    if (field) delete errors[field]
    else Object.keys(errors).forEach(k => delete errors[k])
  }

  function set(field: string, msg: string) { errors[field] = msg }

  /** rules: { 欄位: [是否有錯, 錯誤訊息] }；全部通過回傳 true，否則聚焦第一個錯誤欄位 */
  function check(rules: Record<string, [boolean, string]>): boolean {
    clear()
    for (const [field, [bad, msg]] of Object.entries(rules)) if (bad) errors[field] = msg
    const first = Object.keys(errors)[0]
    if (first) {
      requestAnimationFrame(() =>
        document.querySelector<HTMLElement>(`[data-field="${first}"]`)?.focus())
    }
    return !first
  }

  return { errors, clear, set, check }
}
