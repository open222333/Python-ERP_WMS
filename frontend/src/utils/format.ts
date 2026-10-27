/**
 * [U4] 解析後端時間字串。後端一律以 UTC 儲存，但部分 model（操作紀錄、出入庫單、顧客訂單、
 * 分店等）輸出 isoformat() 時沒有加 'Z'，瀏覽器會把它當成當地時間，台灣顯示早 8 小時。
 * 沒有時區標記的「日期＋時間」字串一律視為 UTC；只有日期、已帶 Z／±hh:mm、或 RFC 1123 格式則照原樣解析。
 */
const NAIVE_DATETIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/
export function parseServerDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const s = String(iso).trim()
  const d = new Date(NAIVE_DATETIME.test(s) ? s.replace(' ', 'T') + 'Z' : s)
  return isNaN(d.getTime()) ? null : d
}

/** 格式化日期時間 */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = parseServerDate(iso) ?? new Date(NaN)
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
  const d = parseServerDate(iso) ?? new Date(NaN)
  if (isNaN(d.getTime())) return iso ?? '—'
  return d.toLocaleDateString('zh-TW')
}
