/** 格式化日期時間 */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-TW', {
    year:   'numeric', month:  '2-digit', day:    '2-digit',
    hour:   '2-digit', minute: '2-digit',
  })
}

/** 格式化金額 */
export function fmtMoney(n: number | null | undefined, symbol = 'NT$'): string {
  if (n == null) return '—'
  return `${symbol} ${n.toLocaleString('zh-TW', { minimumFractionDigits: 0 })}`
}

/** Role 標籤與顏色 */
export const ROLE_COLOR: Record<string, string> = {
  super_admin: 'dark',
  admin:       'danger',
  operator:    'primary',
  cashier:     'warning',
  viewer:      'secondary',
}
export const ROLE_LABEL: Record<string, string> = {
  super_admin: 'Super Admin（超級管理員）',
  admin:       'Admin（管理員）',
  operator:    'Operator（操作員）',
  cashier:     'Cashier（收銀員）',
  viewer:      'Viewer（唯讀）',
}

/** 訂單狀態顏色 */
export const ORDER_STATUS_COLOR: Record<string, string> = {
  pending:    'warning',
  processing: 'primary',
  completed:  'success',
  cancelled:  'secondary',
}
export const ORDER_STATUS_LABEL: Record<string, string> = {
  pending:    '待處理',
  processing: '處理中',
  completed:  '已完成',
  cancelled:  '已取消',
}

/** 簡短日期（只有日期，無時間） */
export function fmtDay(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso ?? '—'
  return d.toLocaleDateString('zh-TW')
}
