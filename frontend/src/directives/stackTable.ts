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
 * - [U13] 卡片排版輔助 class（實際畫面檢查後補上，原本每格都是「標籤：值」一列，卡片過長）：
 *     stack-title   第一個有標籤的文字欄位當卡片標題（不顯示標籤、字級加大）
 *     stack-check   只有勾選框的欄位，浮到卡片右上角
 *     stack-actions 操作欄（表頭為空或「操作」且含按鈕），按鈕靠右排成一列、不顯示標籤
 *     stack-empty   值為空或「—」的欄位，手機上隱藏，減少無資訊的列
 * 桌機版完全不受影響。
 */
import type { Directive } from 'vue'

type StackEl = HTMLTableElement & { __stackObserver?: MutationObserver }

const EMPTY_TEXT = new Set(['', '—', '-', '–'])
const ACTION_LABELS = new Set(['', '操作'])

function toggle(cell: Element, cls: string, on: boolean) {
  if (cell.classList.contains(cls) !== on) cell.classList.toggle(cls, on)
}

function applyLabels(table: HTMLTableElement) {
  const heads = Array.from(table.querySelectorAll('thead tr:last-child th'))
    .map(th => (th.textContent || '').trim())
  table.querySelectorAll('tbody tr').forEach(tr => {
    let col = 0
    let titled = false
    Array.from(tr.children).forEach(cell => {
      const span = Number(cell.getAttribute('colspan')) || 1
      if (span === 1) {
        const label = heads[col] ?? ''
        if (cell.getAttribute('data-label') !== label) cell.setAttribute('data-label', label)

        const text = (cell.textContent || '').trim()
        const hasControl = !!cell.querySelector('button, a, input, select, textarea')
        const onlyCheck = !text && !!cell.querySelector('input[type="checkbox"]')
          && cell.querySelectorAll('button, a, select, textarea, input:not([type="checkbox"])').length === 0
        const isAction = !onlyCheck && ACTION_LABELS.has(label) && !!cell.querySelector('button, a')
        const isEmpty = !hasControl && EMPTY_TEXT.has(text) && !cell.querySelector('img, svg, .badge, .bi')
        const isTitle = !titled && !!label && !!text && !onlyCheck && !isAction
          && !cell.querySelector('input, select, textarea')
        if (isTitle) titled = true

        toggle(cell, 'stack-check', onlyCheck)
        toggle(cell, 'stack-actions', isAction)
        toggle(cell, 'stack-empty', isEmpty && !isTitle)
        toggle(cell, 'stack-title', isTitle)
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
