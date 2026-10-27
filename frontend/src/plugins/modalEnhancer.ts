/**
 * [U6] 自製彈窗共用行為（全站一次套用，不需逐頁修改）
 *
 * 專案的彈窗多為 <div class="modal d-block"> 自製版本（11 個頁面），原本：
 * - 不能按 Esc 關閉
 * - 開啟時背景仍可捲動（手機上手指一滑，後面的頁面跟著捲）
 * - 焦點留在背景頁，鍵盤 Tab 會跑到彈窗後面、螢幕閱讀器不知道彈窗開了
 *
 * 這裡用 MutationObserver 偵測畫面上的彈窗，統一處理：
 * - 有彈窗時鎖住背景捲動（body.app-modal-open）
 * - 新彈窗出現時把焦點移進去，關閉後還原到原本的元素
 * - Tab 只在最上層彈窗內循環
 * - Esc：關閉最上層彈窗（優先點它的 .btn-close；沒有就點遮罩本身，觸發頁面原有的 @click.self 關閉邏輯）
 */
const SELECTOR = '.modal.d-block, .modal-backdrop-custom, .bottom-mask, .center-mask'
const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), ' +
                  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function openModals(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(SELECTOR))
    // getClientRects 為空 = 自己或祖先 display:none（v-show 隱藏的彈窗不算開啟；fixed 元素的 offsetParent 恆為 null 不能用）
    .filter(el => el.getClientRects().length > 0)
}

function topModal(): HTMLElement | null {
  const list = openModals()
  if (!list.length) return null
  // z-index 最高者；相同時取 DOM 中最後一個
  return list.reduce((top, el) =>
    (Number(getComputedStyle(el).zIndex) || 0) >= (Number(getComputedStyle(top).zIndex) || 0) ? el : top)
}

export function installModalEnhancer() {
  if (typeof window === 'undefined' || (window as any).__modalEnhancer) return
  ;(window as any).__modalEnhancer = true

  const opened = new Set<HTMLElement>()                  // 目前開啟中的彈窗
  const returnFocus = new WeakMap<HTMLElement, Element | null>()
  let lastFocused: Element | null = null
  let scheduled = false

  const sync = () => {
    scheduled = false
    const list = openModals()
    document.body.classList.toggle('app-modal-open', list.length > 0)
    // 關閉（移除或 v-show 隱藏）：全部關完後把焦點還給開啟前的元素
    for (const el of Array.from(opened)) {
      if (list.includes(el)) continue
      opened.delete(el)
      const back = returnFocus.get(el)
      if (!list.length && back && document.contains(back)) (back as HTMLElement).focus?.({ preventScroll: true })
    }
    // 新開啟：焦點移進彈窗（優先 autofocus，其次內容區第一個可操作元素）
    for (const el of list) {
      if (opened.has(el)) continue
      opened.add(el)
      returnFocus.set(el, lastFocused)
      if (!el.contains(document.activeElement)) {
        const target = el.querySelector<HTMLElement>('[autofocus]') ||
                       el.querySelector<HTMLElement>(FOCUSABLE.split(', ').map(x => '.modal-body ' + x).join(', ')) ||
                       el.querySelector<HTMLElement>(FOCUSABLE)
        if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1')
        ;(target || el).focus({ preventScroll: true })
      }
    }
  }

  // 記錄彈窗開啟前的焦點，關閉時還原
  document.addEventListener('focusin', (e) => {
    const t = e.target as Element
    if (!t.closest?.(SELECTOR)) lastFocused = t
  })

  // DOM 變動（v-if 加入／移除、v-show 改 style）合併成一次檢查
  new MutationObserver(() => {
    if (scheduled) return
    scheduled = true
    queueMicrotask(sync)
  }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] })

  document.addEventListener('keydown', (e) => {
    const top = topModal()
    if (!top) return
    if (e.key === 'Escape') {
      // [U2] 焦點在有內容的搜尋框時，Esc 交給瀏覽器清空搜尋字，不關彈窗
      const t = e.target as HTMLInputElement
      if (t?.matches?.('input[type="search"]') && t.value) return
      if (e.isComposing) return
      const closeBtn = top.querySelector<HTMLElement>('.btn-close, [data-dismiss], [aria-label="關閉"]')
      if (closeBtn) closeBtn.click()
      else top.dispatchEvent(new MouseEvent('click', { bubbles: true }))   // 觸發 @click.self
      e.preventDefault()
      return
    }
    if (e.key === 'Tab') {
      const items = Array.from(top.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(x => x.getClientRects().length > 0)
      if (!items.length) { e.preventDefault(); return }
      const first = items[0], last = items[items.length - 1]
      if (!top.contains(document.activeElement)) { first.focus(); e.preventDefault() }
      else if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault() }
      else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault() }
    }
  })

  sync()
}
