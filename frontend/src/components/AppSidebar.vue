<script setup>
import { useAuthStore } from '@/stores/auth'
import { useRoute }     from 'vue-router'

const auth  = useAuthStore()
const route = useRoute()

const isActive = (path) => route.path.startsWith(path)

defineEmits(['close'])
</script>

<template>
  <div id="sidebar">
    <div class="brand">
      <i class="bi bi-boxes"></i> WMS 倉儲系統
    </div>

    <div style="overflow-y:auto;flex:1;padding-bottom:8px;">
      <!-- 總覽 -->
      <div class="nav-section">總覽</div>
      <RouterLink class="nav-link" to="/admin/dashboard" :class="{ active: isActive('/admin/dashboard') }">
        <i class="bi bi-grid-1x2"></i> 儀表板
      </RouterLink>

      <!-- 商品管理 -->
      <div class="nav-section">商品管理</div>
      <RouterLink class="nav-link" to="/admin/categories" :class="{ active: isActive('/admin/categories') }">
        <i class="bi bi-tags"></i> 產品分類
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/products" :class="{ active: isActive('/admin/products') }">
        <i class="bi bi-box-seam"></i> 產品資料
      </RouterLink>

      <!-- 倉儲管理 -->
      <div class="nav-section">倉儲管理</div>
      <RouterLink class="nav-link" to="/admin/warehouses" :class="{ active: isActive('/admin/warehouses') }">
        <i class="bi bi-building"></i> 倉庫管理
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/inventory" :class="{ active: isActive('/admin/inventory') }">
        <i class="bi bi-archive"></i> 庫存查詢
      </RouterLink>

      <!-- 出入庫 -->
      <div class="nav-section">出入庫</div>
      <RouterLink class="nav-link" to="/admin/inbound" :class="{ active: isActive('/admin/inbound') }">
        <i class="bi bi-box-arrow-in-down"></i> 入庫管理
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/outbound" :class="{ active: isActive('/admin/outbound') }">
        <i class="bi bi-box-arrow-up"></i> 出庫管理
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/movements" :class="{ active: isActive('/admin/movements') }">
        <i class="bi bi-arrow-left-right"></i> 庫存移動
      </RouterLink>
      <a class="nav-link" href="/quick-io/" target="_blank">
        <i class="bi bi-lightning-charge"></i> 快速出入庫
        <i class="bi bi-box-arrow-up-right ms-1" style="font-size:.65rem"></i>
      </a>

      <!-- 顧客點單 -->
      <div class="nav-section">顧客點單</div>
      <RouterLink class="nav-link" to="/admin/cust-orders" :class="{ active: isActive('/admin/cust-orders') }">
        <i class="bi bi-receipt"></i> 訂單管理
      </RouterLink>
      <a class="nav-link" href="/kitchen/" target="_blank">
        <i class="bi bi-grid-3x3-gap"></i> 備餐顯示
        <i class="bi bi-box-arrow-up-right ms-1" style="font-size:.65rem"></i>
      </a>
      <a class="nav-link" href="/order/" target="_blank">
        <i class="bi bi-qr-code"></i> 顧客點單頁
        <i class="bi bi-box-arrow-up-right ms-1" style="font-size:.65rem"></i>
      </a>

      <!-- POS 收銀 -->
      <div class="nav-section">POS 收銀</div>
      <RouterLink class="nav-link" to="/admin/pos-sales" :class="{ active: isActive('/admin/pos-sales') }">
        <i class="bi bi-receipt"></i> 銷售記錄
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/pos-report" :class="{ active: isActive('/admin/pos-report') }">
        <i class="bi bi-bar-chart-line"></i> 日結報表
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/menus" :class="{ active: isActive('/admin/menus') }">
        <i class="bi bi-menu-button-wide"></i> 菜單管理
      </RouterLink>
      <a class="nav-link" href="/pos/" target="_blank">
        <i class="bi bi-display"></i> 開啟收銀台
        <i class="bi bi-box-arrow-up-right ms-1" style="font-size:.65rem"></i>
      </a>

      <!-- 外送平台 -->
      <div class="nav-section">外送平台</div>
      <RouterLink class="nav-link" to="/admin/delivery" :class="{ active: isActive('/admin/delivery') }">
        <i class="bi bi-scooter"></i> 外送訂單
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/delivery-settings" :class="{ active: isActive('/admin/delivery-settings') }">
        <i class="bi bi-gear"></i> 平台設定
      </RouterLink>

      <!-- 系統 -->
      <div class="nav-section">系統</div>
      <RouterLink v-if="auth.isAdmin" class="nav-link" to="/admin/users" :class="{ active: isActive('/admin/users') }">
        <i class="bi bi-people"></i> 使用者管理
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/logs" :class="{ active: isActive('/admin/logs') }">
        <i class="bi bi-journal-text"></i> 操作紀錄
      </RouterLink>
      <RouterLink class="nav-link" to="/admin/settings" :class="{ active: isActive('/admin/settings') }">
        <i class="bi bi-sliders"></i> 系統設定
      </RouterLink>
      <a class="nav-link" href="/docs/" target="_blank">
        <i class="bi bi-book"></i> 使用說明
        <i class="bi bi-box-arrow-up-right ms-1" style="font-size:.65rem"></i>
      </a>
    </div>

    <div id="sidebar-footer">
      <i class="bi bi-person-circle me-1"></i>
      <span>{{ auth.displayName || auth.username }}</span>
      <span class="badge bg-secondary ms-1 float-end">{{ auth.role }}</span>
    </div>
  </div>
</template>

<style scoped>
#sidebar {
  position: fixed; top: 0; left: 0;
  width: var(--sidebar-w); height: 100vh;
  background: var(--sidebar-bg);
  display: flex; flex-direction: column;
  z-index: 1050; transition: transform .25s;
}
.brand {
  padding: 20px 18px 12px; color: #fff; font-weight: 700;
  font-size: 1.1rem; letter-spacing: .5px;
  border-bottom: 1px solid rgba(255,255,255,.08);
  display: flex; align-items: center; gap: 8px;
}
.brand i { color: var(--accent); font-size: 1.4rem; }
.nav-section {
  font-size: .72rem; color: rgba(255,255,255,.35);
  padding: 14px 18px 4px; letter-spacing: 1px; text-transform: uppercase;
}
.nav-link {
  color: rgba(255,255,255,.7); padding: 9px 18px; border-radius: 6px;
  margin: 1px 8px; display: flex; align-items: center; gap: 10px;
  transition: all .15s; cursor: pointer; text-decoration: none;
}
.nav-link i { width: 18px; text-align: center; font-size: 1rem; }
.nav-link:hover, .nav-link.active { background: var(--sidebar-hover); color: #fff; }
.nav-link.active { background: var(--accent); }
#sidebar-footer {
  margin-top: auto; padding: 12px 18px;
  border-top: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.5); font-size: .8rem;
}
@media(max-width:768px) {
  #sidebar { transform: translateX(-100%); }
  #sidebar.open { transform: translateX(0); }
}
</style>
