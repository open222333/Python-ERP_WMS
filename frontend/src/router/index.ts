import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const APP = 'WMS'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/admin/dashboard' },
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { title: '登入' } },

    // ── Admin （需要登入）────────────────────────────────
    {
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '',          redirect: '/admin/dashboard' },
        { path: 'dashboard',         component: () => import('@/views/admin/DashboardView.vue'),       meta: { title: '總覽' } },
        { path: 'categories',        component: () => import('@/views/admin/CategoriesView.vue'),      meta: { title: '分類管理' } },
        { path: 'products',          component: () => import('@/views/admin/ProductsView.vue'),        meta: { title: '商品管理' } },
        { path: 'warehouses',        component: () => import('@/views/admin/WarehousesView.vue'),      meta: { title: '倉庫管理' } },
        { path: 'inventory',         component: () => import('@/views/admin/InventoryView.vue'),       meta: { title: '庫存管理' } },
        { path: 'inbound',           component: () => import('@/views/admin/InboundView.vue'),         meta: { title: '入庫管理' } },
        { path: 'outbound',          component: () => import('@/views/admin/OutboundView.vue'),        meta: { title: '出庫管理' } },
        { path: 'movements',         component: () => import('@/views/admin/MovementsView.vue'),       meta: { title: '出入庫紀錄' } },
        { path: 'cust-orders',       component: () => import('@/views/admin/CustOrdersView.vue'),     meta: { title: '顧客訂單' } },
        { path: 'pos-sales',         component: () => import('@/views/admin/PosSalesView.vue'),       meta: { title: 'POS 銷售紀錄' } },
        { path: 'pos-report',        component: () => import('@/views/admin/PosReportView.vue'),      meta: { title: 'POS 報表' } },
        { path: 'menus',             component: () => import('@/views/admin/MenusView.vue'),          meta: { title: '菜單管理' } },
        { path: 'delivery-orders',   component: () => import('@/views/admin/DeliveryOrdersView.vue'),  meta: { title: '外送訂單' } },
        { path: 'delivery-settings', component: () => import('@/views/admin/DeliverySettingsView.vue'), meta: { title: '外送設定' } },
        { path: 'users',             component: () => import('@/views/admin/UsersView.vue'),          meta: { title: '使用者管理' } },
        { path: 'logs',              component: () => import('@/views/admin/LogsView.vue'),           meta: { title: '操作紀錄' } },
        { path: 'settings',          component: () => import('@/views/admin/SettingsView.vue'),       meta: { title: '系統設定' } },
        { path: 'qr-codes',          component: () => import('@/views/admin/QrCodesView.vue'),        meta: { title: 'QR 碼管理' } },
        { path: 'invoices',          component: () => import('@/views/admin/InvoicesView.vue'),       meta: { title: '發票管理' } },
        { path: 'invoice-settings',  component: () => import('@/views/admin/InvoiceSettingsView.vue'), meta: { title: '發票設定' } },
      ],
    },

    // ── 獨立頁面 ────────────────────────────────────────
    { path: '/pos',      component: () => import('@/views/PosView.vue'),      meta: { requiresAuth: true, title: 'POS 收銀台' } },
    { path: '/quick-io', component: () => import('@/views/QuickIoView.vue'),  meta: { requiresAuth: true, title: '快速出入庫' } },
    { path: '/kitchen',  component: () => import('@/views/KitchenView.vue'),  meta: { title: '備餐顯示' } },
    { path: '/order',    component: () => import('@/views/OrderView.vue'),    meta: { title: '顧客點餐' } },

    // ── 404 ─────────────────────────────────────────────
    { path: '/:pathMatch(.*)*', redirect: '/admin/dashboard' },
  ],
})

// ── Bootstrap modal 殘留清理 ──────────────────────────────
// Bootstrap JS 開 modal 時會在 <body> 插入 .modal-backdrop 並加 modal-open class。
// Vue Router 導航只銷毀 Vue 元件，Bootstrap 的副作用不會自動清除，導致頁面卡住。
router.afterEach((to) => {
  document.querySelectorAll('.modal-backdrop').forEach(el => el.remove())
  document.body.classList.remove('modal-open')
  document.body.style.removeProperty('overflow')
  document.body.style.removeProperty('padding-right')

  const pageTitle = to.matched.map(r => r.meta?.title).filter(Boolean).at(-1) as string | undefined
  document.title = pageTitle ? `${pageTitle} — ${APP}` : APP
})

// ── Navigation Guard ──────────────────────────────────────
router.beforeEach(async to => {
  if (!to.meta.requiresAuth) return true

  const auth = useAuthStore()

  // 還沒有 token → 去登入
  if (!auth.token) return '/login'

  // 有 token 但還沒拿到 /me 資料 → 先 fetchMe
  if (!auth.ready) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return '/login'
    }
  }

  return true
})

export default router
