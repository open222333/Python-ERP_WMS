<template>
  <div class="d-flex" style="min-height:100vh">
    <!-- ─── Sidebar ─────────────────────────────────────── -->
    <nav id="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="brand">
        <i class="bi bi-boxes"></i>
        <span class="brand-text">WMS 系統</span>
      </div>

      <div class="sidebar-scroll">
        <!-- 儀表板 -->
        <RouterLink to="/admin/dashboard" class="nav-link" @click="closeMobile">
          <i class="bi bi-grid-1x2"></i><span>儀表板</span>
        </RouterLink>

        <!-- 商品管理 -->
        <template v-if="auth.pageVisible('categories') || auth.pageVisible('products')">
          <div class="nav-section">商品管理</div>
          <RouterLink v-if="auth.pageVisible('categories')" to="/admin/categories" class="nav-link" @click="closeMobile">
            <i class="bi bi-tags"></i><span>產品分類</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('products')" to="/admin/products" class="nav-link" @click="closeMobile">
            <i class="bi bi-box-seam"></i><span>產品資料</span>
          </RouterLink>
        </template>

        <!-- 倉儲管理 -->
        <template v-if="auth.pageVisible('warehouses') || auth.pageVisible('inventory')">
          <div class="nav-section">倉儲管理</div>
          <RouterLink v-if="auth.pageVisible('warehouses')" to="/admin/warehouses" class="nav-link" @click="closeMobile">
            <i class="bi bi-building"></i><span>倉庫管理</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('inventory')" to="/admin/inventory" class="nav-link" @click="closeMobile">
            <i class="bi bi-archive"></i><span>庫存查詢</span>
          </RouterLink>
        </template>

        <!-- 出入庫 -->
        <template v-if="auth.pageVisible('inbound') || auth.pageVisible('outbound') || auth.pageVisible('movements') || auth.pageVisible('quick-io')">
          <div class="nav-section">出入庫</div>
          <RouterLink v-if="auth.pageVisible('inbound')"   to="/admin/inbound"   class="nav-link" @click="closeMobile">
            <i class="bi bi-box-arrow-in-down"></i><span>入庫管理</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('outbound')"  to="/admin/outbound"  class="nav-link" @click="closeMobile">
            <i class="bi bi-box-arrow-up"></i><span>出庫管理</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('movements')" to="/admin/movements" class="nav-link" @click="closeMobile">
            <i class="bi bi-arrow-left-right"></i><span>庫存移動</span>
          </RouterLink>
          <a v-if="auth.pageVisible('quick-io')" href="/quick-io" target="_blank" class="nav-link external">
            <i class="bi bi-lightning-charge"></i><span>快速出入庫</span>
            <i class="bi bi-box-arrow-up-right ext-icon"></i>
          </a>
        </template>

        <!-- 顧客點單 -->
        <template v-if="auth.pageVisible('cust-orders') || auth.pageVisible('kitchen-link') || auth.pageVisible('order-link')">
          <div class="nav-section">顧客點單</div>
          <RouterLink v-if="auth.pageVisible('cust-orders')" to="/admin/cust-orders" class="nav-link" @click="closeMobile">
            <i class="bi bi-receipt"></i><span>訂單管理</span>
          </RouterLink>
          <a v-if="auth.pageVisible('kitchen-link')" href="/kitchen" target="_blank" class="nav-link external">
            <i class="bi bi-grid-3x3-gap"></i><span>備餐顯示</span>
            <i class="bi bi-box-arrow-up-right ext-icon"></i>
          </a>
          <a v-if="auth.pageVisible('order-link')" href="/order" target="_blank" class="nav-link external">
            <i class="bi bi-qr-code"></i><span>顧客點單頁</span>
            <i class="bi bi-box-arrow-up-right ext-icon"></i>
          </a>
        </template>

        <!-- POS 收銀 -->
        <template v-if="auth.pageVisible('pos-sales') || auth.pageVisible('pos-report') || auth.pageVisible('menus') || auth.pageVisible('pos-link')">
          <div class="nav-section">POS 收銀</div>
          <RouterLink v-if="auth.pageVisible('pos-sales')"   to="/admin/pos-sales"   class="nav-link" @click="closeMobile">
            <i class="bi bi-receipt"></i><span>銷售記錄</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('pos-report')"  to="/admin/pos-report"  class="nav-link" @click="closeMobile">
            <i class="bi bi-bar-chart-line"></i><span>銷售報表</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('menus')"       to="/admin/menus"       class="nav-link" @click="closeMobile">
            <i class="bi bi-menu-button-wide"></i><span>菜單管理</span>
          </RouterLink>
          <a v-if="auth.pageVisible('pos-link')" href="/pos" target="_blank" class="nav-link external">
            <i class="bi bi-display"></i><span>開啟收銀台</span>
            <i class="bi bi-box-arrow-up-right ext-icon"></i>
          </a>
        </template>

        <!-- 外送平台 -->
        <template v-if="auth.pageVisible('delivery-orders') || auth.pageVisible('delivery-settings')">
          <div class="nav-section">外送平台</div>
          <RouterLink v-if="auth.pageVisible('delivery-orders')"   to="/admin/delivery-orders"   class="nav-link" @click="closeMobile">
            <i class="bi bi-scooter"></i><span>外送訂單</span>
          </RouterLink>
          <RouterLink v-if="auth.pageVisible('delivery-settings')" to="/admin/delivery-settings" class="nav-link" @click="closeMobile">
            <i class="bi bi-gear"></i><span>平台設定</span>
          </RouterLink>
        </template>

        <!-- 系統（依角色 / 模板設定顯示） -->
        <template v-if="auth.isAdmin || auth.pageVisible('users') || auth.pageVisible('logs') || auth.pageVisible('settings')">
          <div class="nav-section">系統</div>
          <RouterLink v-if="auth.isAdmin || auth.pageVisible('users')" to="/admin/users" class="nav-link" @click="closeMobile">
            <i class="bi bi-people"></i><span>使用者管理</span>
          </RouterLink>
          <RouterLink v-if="auth.isAdmin || auth.pageVisible('logs')" to="/admin/logs" class="nav-link" @click="closeMobile">
            <i class="bi bi-journal-text"></i><span>操作紀錄</span>
          </RouterLink>
          <RouterLink v-if="auth.isAdmin || auth.pageVisible('settings')" to="/admin/settings" class="nav-link" @click="closeMobile">
            <i class="bi bi-sliders"></i><span>系統設定</span>
          </RouterLink>
        </template>
      </div>

      <div class="sidebar-footer">
        <span class="text-truncate">{{ auth.username }}</span>
        <span class="badge rounded-pill" :class="`bg-${roleColor}`">{{ auth.role }}</span>
      </div>
    </nav>

    <!-- ─── Main ───────────────────────────────────────── -->
    <div id="main-area">
      <!-- Topbar -->
      <header id="topbar">
        <div class="d-flex align-items-center gap-2">
          <button class="btn btn-sm btn-outline-secondary d-lg-none" @click="sidebarCollapsed = !sidebarCollapsed">
            <i class="bi bi-list"></i>
          </button>
          <button class="btn btn-sm btn-outline-secondary d-none d-lg-block" @click="sidebarCollapsed = !sidebarCollapsed" title="折疊側邊欄">
            <i class="bi" :class="sidebarCollapsed ? 'bi-layout-sidebar' : 'bi-layout-sidebar-inset'"></i>
          </button>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="d-flex align-items-center gap-2">
          <RouterLink to="/admin/settings" class="btn btn-sm btn-outline-secondary" title="系統設定">
            <i class="bi bi-sliders"></i>
          </RouterLink>
          <button class="btn btn-sm btn-outline-danger" @click="handleLogout" title="登出">
            <i class="bi bi-box-arrow-right"></i>
          </button>
        </div>
      </header>

      <!-- Page content -->
      <main id="content">
        <RouterView />
      </main>
    </div>

    <!-- Mobile overlay -->
    <div
      v-if="!sidebarCollapsed"
      class="sidebar-overlay d-lg-none"
      @click="sidebarCollapsed = true"
    />
  </div>

  <AppToast />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCacheStore } from '@/stores/cache'
import AppToast from '@/components/AppToast.vue'

const auth   = useAuthStore()
const cache  = useCacheStore()
const router = useRouter()
const route  = useRoute()

const sidebarCollapsed = ref(false)

// ── 監聽 401 未授權事件（由 api/index.ts 發出）────────
function _onUnauthorized() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  window.addEventListener('app:unauthorized', _onUnauthorized)
  // Refresh user info from server and prefetch common data
  await auth.fetchMe()
  cache.loadAll().catch(() => {})
})

onUnmounted(() => {
  window.removeEventListener('app:unauthorized', _onUnauthorized)
})

function closeMobile() {
  // 手機版點選後收起
  if (window.innerWidth < 992) sidebarCollapsed.value = true
}

// 頁面標題對映
const PAGE_TITLES: Record<string, string> = {
  '/admin/dashboard':         '儀表板',
  '/admin/categories':        '產品分類',
  '/admin/products':          '產品資料',
  '/admin/warehouses':        '倉庫管理',
  '/admin/inventory':         '庫存查詢',
  '/admin/inbound':           '入庫管理',
  '/admin/outbound':          '出庫管理',
  '/admin/movements':         '庫存移動',
  '/admin/cust-orders':       '訂單管理',
  '/admin/pos-sales':         '銷售記錄',
  '/admin/pos-report':        '銷售報表',
  '/admin/menus':             '菜單管理',
  '/admin/delivery-orders':   '外送訂單',
  '/admin/delivery-settings': '平台設定',
  '/admin/users':             '使用者管理',
  '/admin/logs':              '操作紀錄',
  '/admin/settings':          '系統設定',
}
const pageTitle = computed(() => PAGE_TITLES[route.path] ?? 'WMS')

const roleColor = computed(() => ({
  admin: 'danger', operator: 'primary', viewer: 'secondary',
}[auth.role ?? 'viewer'] ?? 'secondary'))

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
:root {
  --sidebar-w:   220px;
  --sidebar-bg:  #1a1d2e;
  --sidebar-hover: #2d3250;
  --accent:      #5c7cfa;
}

#sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  overflow: hidden;
  transition: width .2s, min-width .2s;
  z-index: 1040;
}
#sidebar.collapsed {
  width: 0;
  min-width: 0;
}
.brand {
  padding: 18px 16px 12px;
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  border-bottom: 1px solid rgba(255,255,255,.08);
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.brand i { color: var(--accent); font-size: 1.3rem; }
.brand-text { overflow: hidden; }

.sidebar-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
}
.sidebar-scroll::-webkit-scrollbar { width: 4px; }
.sidebar-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,.15); border-radius: 2px; }

.nav-section {
  font-size: .68rem;
  color: rgba(255,255,255,.35);
  padding: 12px 16px 3px;
  letter-spacing: 1px;
  text-transform: uppercase;
  white-space: nowrap;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 9px;
  color: rgba(255,255,255,.7);
  padding: 8px 16px;
  border-radius: 6px;
  margin: 1px 8px;
  text-decoration: none;
  transition: all .15s;
  white-space: nowrap;
  font-size: .88rem;
}
.nav-link:hover { background: var(--sidebar-hover); color: #fff; }
.nav-link.router-link-active { background: var(--accent); color: #fff; }
.nav-link.external.router-link-active { background: var(--sidebar-hover); color: rgba(255,255,255,.9); }
.nav-link i { width: 18px; text-align: center; flex-shrink: 0; }
.ext-icon { font-size: .6rem; margin-left: auto; opacity: .6; }

.sidebar-footer {
  padding: 10px 16px;
  border-top: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.55);
  font-size: .78rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  white-space: nowrap;
}

#main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
#topbar {
  background: #fff;
  border-bottom: 1px solid #e9ecef;
  padding: 0 20px;
  height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}
.page-title { font-weight: 600; font-size: .95rem; color: #333; }

#content { padding: 20px; flex: 1; background: #f4f6fb; }

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.4);
  z-index: 1039;
}

/* 手機：sidebar 用 fixed overlay */
@media (max-width: 991px) {
  #sidebar {
    position: fixed;
    top: 0; left: 0;
    height: 100vh;
    transform: translateX(0);
    transition: transform .25s;
  }
  #sidebar.collapsed { transform: translateX(-100%); width: var(--sidebar-w); min-width: var(--sidebar-w); }
}
</style>
