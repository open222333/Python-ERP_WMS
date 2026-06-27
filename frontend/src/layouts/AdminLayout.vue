<template>
  <div class="d-flex" style="min-height:100vh"
       :class="{ 'admin-dark': theme.darkMode }"
       :data-bs-theme="theme.darkMode ? 'dark' : 'light'">
    <!-- ─── Sidebar ─────────────────────────────────────── -->
    <nav id="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="brand">
        <i class="bi bi-boxes"></i>
        <span class="brand-text">WMS 系統</span>
      </div>

      <div class="sidebar-scroll">
        <!-- 動態渲染：從 src/config/nav.ts 讀取，新增頁面只需改 nav.ts -->
        <template v-for="section in visibleSections" :key="section.label">
          <div class="nav-section">{{ section.label }}</div>
          <template v-for="group in section.groups" :key="group.sub || '__main__'">
            <div v-if="group.sub" class="nav-subsection">{{ group.sub }}</div>
            <template v-for="item in group.items" :key="item.key">
              <RouterLink
                v-if="item.to"
                class="nav-link"
                :to="item.to"
                @click="closeMobile"
              >
                <i :class="['bi', item.icon]"></i><span>{{ item.label }}</span>
              </RouterLink>
              <a
                v-else-if="item.href"
                class="nav-link external"
                :href="item.href"
                target="_blank"
                @click="closeMobile"
              >
                <i :class="['bi', item.icon]"></i><span>{{ item.label }}</span>
                <i class="bi bi-box-arrow-up-right ext-icon"></i>
              </a>
            </template>
          </template>
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
import { useThemeStore } from '@/stores/theme'
import { NAV_CONFIG } from '@/config/nav'
import AppToast from '@/components/AppToast.vue'

const auth   = useAuthStore()
const cache  = useCacheStore()
const theme  = useThemeStore()
const router = useRouter()
const route  = useRoute()

const sidebarCollapsed = ref(false)

function isVisible(item: any) {
  if (item.adminOnly)  return auth.isAdmin
  if (item.alwaysShow) return true
  return auth.pageVisible(item.key)
}

function buildGroups(items: any[]) {
  const result: { sub: string | null; items: any[] }[] = []
  let current: { sub: string | null; items: any[] } | null = null
  for (const item of items) {
    const sub = item.sub ?? null
    if (!current || current.sub !== sub) {
      current = { sub, items: [] }
      result.push(current)
    }
    current.items.push(item)
  }
  return result
}

const visibleSections = computed(() =>
  NAV_CONFIG
    .map(section => {
      const items = section.items.filter(isVisible)
      if (!items.length) return null
      return { label: section.label, groups: buildGroups(items) }
    })
    .filter(Boolean)
)

// ── 監聽 401 未授權事件（由 api/index.ts 發出）────────
function _onUnauthorized() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  theme.applyTheme(theme.themeId)          // restore saved theme
  window.addEventListener('app:unauthorized', _onUnauthorized)
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

// 頁面標題從 nav.ts 自動產生，避免與 nav.ts 不一致
const PAGE_TITLES: Record<string, string> = Object.fromEntries(
  NAV_CONFIG.flatMap(s => s.items)
    .filter(item => item.to)
    .map(item => [item.to, item.label])
)
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
.nav-subsection {
  font-size: .65rem;
  color: rgba(255,255,255,.25);
  padding: 8px 16px 2px 24px;
  letter-spacing: .5px;
  white-space: nowrap;
}
.nav-link-sub { margin-left: 10px; }
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
  background: var(--topbar-bg, #fff);
  border-bottom: 1px solid var(--topbar-border, #e9ecef);
  padding: 0 20px;
  height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}
.page-title { font-weight: 600; font-size: .95rem; color: var(--text-main, #333); }

#content { padding: 20px; flex: 1; background: var(--content-bg, #f4f6fb); }

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
