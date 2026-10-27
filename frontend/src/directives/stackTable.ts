/**
 * [MOBILE] v-stack-table：手機上把表格的每一列改成卡片
 *
 * 用法：<table class="table" v-stack-table>
 * - 自動讀取 <thead> 的欄位名稱，寫到每個 <td> 的 data-label
 * - 搭配 style.css 的 .table-stack 規則：寬度 < 768px 時隱藏表頭，
 *   每列變成一張卡片，每格前面顯示欄位名稱（::before）
 * - 有 colspan 的格子（載入中、無資料）不加標籤、置中顯示
 * - 表頭文字為空的欄位（勾選框、操作按鈕）不顯示標籤
 * - 列表內容變動時（篩選、分頁、重新載入）自動重新標記
 * 桌機版完全不受影響。
 */
import type { Directive } from 'vue'

type StackEl = HTMLTableElement & { __stackObserver?: MutationObserver }

function applyLabels(table: HTMLTableElement) {
  const heads = Array.from(table.querySelectorAll('thead tr:last-child th'))
    .map(th => (th.textContent || '').trim())
  table.querySelectorAll('tbody tr').forEach(tr => {
    let col = 0
    Array.from(tr.children).forEach(cell => {
      const span = Number(cell.getAttribute('colspan')) || 1
      if (span === 1) {
        const label = heads[col] ?? ''
        if (cell.getAttribute('data-label') !== label) cell.setAttribute('data-label', label)
      }
      col += span
    })
  })
}

export const vStackTable: Directive<StackEl> = {
  mounted(el) {
    el.classList.add('table-stack')
    applyLabels(el)
    // 只監聽節點增刪（不監聽屬性），寫入 data-label 不會再觸發自己
    el.__stackObserver = new MutationObserver(() => applyLabels(el))
    el.__stackObserver.observe(el, { childList: true, subtree: true, characterData: true })
  },
  updated(el) {
    applyLabels(el)
  },
  unmounted(el) {
    el.__stackObserver?.disconnect()
  },
}
