import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/admin/dashboard' },
    { path: '/login', component: () => import('@/views/LoginView.vue') },

    // ── Admin （需要登入）────────────────────────────────
    {
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '',          redirect: '/admin/dashboard' },
        { path: 'dashboard',          component: () => import('@/views/admin/DashboardView.vue') },
        { path: 'categories',         component: () => import('@/views/admin/CategoriesView.vue') },
        { path: 'products',           component: () => import('@/views/admin/ProductsView.vue') },
        { path: 'warehouses',         component: () => import('@/views/admin/WarehousesView.vue') },
        { path: 'inventory',          component: () => import('@/views/admin/InventoryView.vue') },
        { path: 'inbound',            component: () => import('@/views/admin/InboundView.vue') },
        { path: 'outbound',           component: () => import('@/views/admin/OutboundView.vue') },
        { path: 'movements',          component: () => import('@/views/admin/MovementsView.vue') },
        { path: 'cust-orders',        component: () => import('@/views/admin/CustOrdersView.vue') },
        { path: 'pos-sales',          component: () => import('@/views/admin/PosSalesView.vue') },
        { path: 'pos-report',         component: () => import('@/views/admin/PosReportView.vue') },
        { path: 'menus',              component: () => import('@/views/admin/MenusView.vue') },
        { path: 'delivery-orders',    component: () => import('@/views/admin/DeliveryOrdersView.vue') },
        { path: 'delivery-settings',  component: () => import('@/views/admin/DeliverySettingsView.vue') },
        { path: 'users',              component: () => import('@/views/admin/UsersView.vue') },
        { path: 'logs',               component: () => import('@/views/admin/LogsView.vue') },
        { path: 'settings',           component: () => import('@/views/admin/SettingsView.vue') },
        { path: 'qr-codes',           component: () => import('@/views/admin/QrCodesView.vue') },
        { path: 'invoices',           component: () => import('@/views/admin/InvoicesView.vue') },
        { path: 'invoice-settings',   component: () => import('@/views/admin/InvoiceSettingsView.vue') },
      ],
    },

    // ── 獨立頁面 ────────────────────────────────────────
    { path: '/pos',      component: () => import('@/views/PosView.vue'),      meta: { requiresAuth: true } },
    { path: '/quick-io', component: () => import('@/views/QuickIoView.vue'),  meta: { requiresAuth: true } },
    { path: '/kitchen',  component: () => import('@/views/KitchenView.vue')  },   // 無需登入
    { path: '/order',    component: () => import('@/views/OrderView.vue')    },   // 無需登入

    // ── 404 ─────────────────────────────────────────────
    { path: '/:pathMatch(.*)*', redirect: '/admin/dashboard' },
  ],
})

// ── Bootstrap modal 殘留清理 ──────────────────────────────
// Bootstrap JS 開 modal 時會在 <body> 插入 .modal-backdrop 並加 modal-open class。
// Vue Router 導航只銷毀 Vue 元件，Bootstrap 的副作用不會自動清除，導致頁面卡住。
router.afterEach(() => {
  document.querySelectorAll('.modal-backdrop').forEach(el => el.remove())
  document.body.classList.remove('modal-open')
  document.body.style.removeProperty('overflow')
  document.body.style.removeProperty('padding-right')
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
