/**
 * 側欄導覽設定 — 唯一資料來源
 *
 * 新增頁面只需在此加一筆，AdminLayout 側欄和使用者模板頁面設定
 * 都會自動同步，不需要額外修改其他檔案。
 *
 * 欄位說明：
 *   key            — pageVisible(key) 對應鍵，也是模板 pages_enabled 的 key
 *   label          — 顯示名稱
 *   icon           — Bootstrap Icons class（不含 'bi ' 前綴）
 *   to             — 內部路由（RouterLink）
 *   href           — 外部連結（新分頁開啟）
 *   sub            — 側欄子章節標題（相同 sub 值的連續項目會收在同一標題下）
 *   system         — 模板預設值為 false（admin 帳號預設 true）
 *   adminOnly      — 側欄只對 admin role 顯示，不走 pageVisible
 *   alwaysShow     — 側欄永遠顯示，不走 pageVisible，也不進模板設定
 *   hideFromConfig — 側欄仍走 pageVisible，但不出現在模板設定頁
 *   configGroup    — 模板設定中的分組名稱（覆蓋預設的 section.label）
 */

export interface NavItem {
  key:             string
  label:           string
  icon:            string
  to?:             string
  href?:           string
  sub?:            string
  system?:         boolean
  adminOnly?:      boolean
  alwaysShow?:     boolean
  hideFromConfig?: boolean
  configGroup?:    string
}

export interface NavSection {
  label: string
  items: NavItem[]
}

export const NAV_CONFIG: NavSection[] = [
  {
    label: '總覽',
    items: [
      { key: 'dashboard', label: '儀表板', icon: 'bi-grid-1x2', to: '/admin/dashboard' },
    ],
  },
  {
    label: '倉儲管理',
    items: [
      { key: 'products',  label: '產品資料',   icon: 'bi-box-seam',          to: '/admin/products' },
      { key: 'warehouses', label: '倉庫管理',  icon: 'bi-building',          to: '/admin/warehouses' },
      { key: 'inventory',  label: '庫存查詢',  icon: 'bi-archive',           to: '/admin/inventory' },
      { key: 'inbound',    label: '入庫管理',  icon: 'bi-box-arrow-in-down', to: '/admin/inbound',  sub: '出入庫', hideFromConfig: true },
      { key: 'outbound',   label: '出庫管理',  icon: 'bi-box-arrow-up',      to: '/admin/outbound', sub: '出入庫', hideFromConfig: true },
      { key: 'movements',  label: '庫存移動',  icon: 'bi-arrow-left-right',  to: '/admin/movements' },
      { key: 'quick-io',   label: '快速出入庫', icon: 'bi-lightning-charge', href: '/quick-io/' },
    ],
  },
  {
    label: '前台',
    items: [
      { key: 'pos-link',        label: '開啟收銀台', icon: 'bi-display',        href: '/pos/' },
      { key: 'order-link',      label: '顧客點單頁', icon: 'bi-qr-code',        href: '/order/' },
      { key: 'kitchen-link',    label: '備餐顯示',   icon: 'bi-grid-3x3-gap',   href: '/kitchen/' },
      { key: 'cust-orders',     label: '訂單管理',   icon: 'bi-receipt',         to: '/admin/cust-orders' },
      { key: 'delivery-orders', label: '外送訂單管理', icon: 'bi-scooter',       to: '/admin/delivery-orders' },
    ],
  },
  {
    label: '財務',
    items: [
      { key: 'pos-sales',  label: '銷售記錄', icon: 'bi-receipt',           to: '/admin/pos-sales' },
      { key: 'pos-report', label: '日結報表', icon: 'bi-bar-chart-line',    to: '/admin/pos-report' },
      { key: 'invoices',   label: '電子發票', icon: 'bi-file-earmark-text', to: '/admin/invoices' },
    ],
  },
  {
    label: '系統',
    items: [
      { key: 'stores',            label: '分店管理',   icon: 'bi-shop',            to: '/admin/stores',           adminOnly: true },
      { key: 'users',             label: '使用者管理', icon: 'bi-people',          to: '/admin/users',            system: true },
      { key: 'menus',             label: '菜單管理',   icon: 'bi-menu-button-wide', to: '/admin/menus' },
      { key: 'invoice-settings',  label: '發票設定',   icon: 'bi-receipt-cutoff',  to: '/admin/invoice-settings', system: true },
      { key: 'delivery-settings', label: '外送平台設定', icon: 'bi-gear',          to: '/admin/delivery-settings', system: true },
      { key: 'logs',              label: '操作紀錄',   icon: 'bi-journal-text',    to: '/admin/logs',             system: true },
      { key: 'settings',          label: '系統設定',   icon: 'bi-sliders',         to: '/admin/settings' },
      { key: 'docs-link',         label: '使用說明',   icon: 'bi-book',            href: '/docs/',                alwaysShow: true },
    ],
  },
]

/**
 * 可在使用者模板中配置顯示/隱藏的頁面清單。
 *
 * 排除條件（任一）：
 *   - alwaysShow    → 固定顯示，無需設定
 *   - adminOnly     → 純由 role 控制，無需設定
 *   - hideFromConfig→ 明確標記不進設定清單
 *
 * group 優先順序：configGroup → sub → section.label
 */
export const CONFIGURABLE_PAGES = NAV_CONFIG.flatMap(section =>
  section.items
    .filter(item => !item.alwaysShow && !item.adminOnly && !item.hideFromConfig)
    .map(item => ({
      key:    item.key,
      label:  item.label,
      group:  item.configGroup ?? item.sub ?? section.label,
      system: item.system,
    }))
)
