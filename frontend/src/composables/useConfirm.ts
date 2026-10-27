/**
 * [U5] 共用確認框／提示框，取代瀏覽器原生 confirm()／alert()
 *
 *   if (!(await appConfirm('確定要刪除此產品？', { danger: true }))) return
 *   await appAlert('送出失敗，請重試')
 *
 * 畫面由 components/AppConfirm.vue（掛在 App.vue，全站一個）負責顯示。
 * 原生框樣式無法控制、手機上體驗差，且顧客點餐頁也在用。
 */
import { reactive } from 'vue'

export interface ConfirmOptions {
  title?: string
  okText?: string
  cancelText?: string
  danger?: boolean        // 確認鈕用紅色（刪除、清除、退款等不可逆操作）
}

interface DialogState extends Required<Omit<ConfirmOptions, 'title'>> {
  open: boolean
  title: string
  message: string
  alertOnly: boolean
  resolve: ((ok: boolean) => void) | null
}

export const dialogState = reactive<DialogState>({
  open: false, title: '', message: '', alertOnly: false,
  okText: '確定', cancelText: '取消', danger: false, resolve: null,
})

function openDialog(message: string, opts: ConfirmOptions, alertOnly: boolean): Promise<boolean> {
  // 前一個還開著時先以「取消」結束，避免 Promise 永遠不 resolve
  dialogState.resolve?.(false)
  return new Promise(resolve => {
    Object.assign(dialogState, {
      open: true, message, alertOnly,
      title: opts.title ?? (alertOnly ? '提示' : '請確認'),
      okText: opts.okText ?? '確定',
      cancelText: opts.cancelText ?? '取消',
      danger: opts.danger ?? false,
      resolve,
    })
  })
}

export function appConfirm(message: string, opts: ConfirmOptions = {}): Promise<boolean> {
  return openDialog(message, opts, false)
}

export function appAlert(message: string, opts: ConfirmOptions = {}): Promise<void> {
  return openDialog(message, opts, true).then(() => undefined)
}

export function closeDialog(ok: boolean) {
  const r = dialogState.resolve
  dialogState.open = false
  dialogState.resolve = null
  r?.(ok)
}
