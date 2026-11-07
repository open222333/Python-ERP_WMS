<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import http from '@/api'
import { appAlert } from '@/composables/useConfirm'
// [U10] 2026-11 拆分：購物車列、我的訂單、客製化抽屜、底部抽屜外框移至 components/order/
import { selKey, rowPrice, type SelectionItem, type CartRow } from '@/components/order/orderCart'
import OrderBottomSheet from '@/components/order/OrderBottomSheet.vue'
import OrderCartRows from '@/components/order/OrderCartRows.vue'
import MyOrdersList from '@/components/order/MyOrdersList.vue'
import OrderCustomizeSheet from '@/components/order/OrderCustomizeSheet.vue'

const auth  = useAuthStore()
const route = useRoute()

// QR Token（新模式）或桌號（舊模式，相容）
const qrToken      = computed(() => ((route.query.t     as string) || '').trim())
const tableFromUrl = computed(() => ((route.query.table as string) || '').trim())

// 後端解析後的桌號（token 模式由 /menu 回傳）
const resolvedTable  = ref('')
// 同桌共用 session token（Redis-backed，存 localStorage 供頁面重整後恢復）
const sessionToken   = ref(localStorage.getItem('order_session_token') || '')

// SSE：顧客點餐即時推播
const myOrders      = ref<any[]>([])
const sessionClosed = ref(false)
let   sseConn: EventSource | null = null

// ── 登入 ──────────────────────────────────────────
const loginForm    = reactive({ username: '', password: '' })
const loginLoading = ref(false)
const loginError   = ref('')

async function doLogin() {
  loginLoading.value = true
  loginError.value   = ''
  try {
    await auth.login(loginForm.username, loginForm.password)
    await loadMenu()
  } catch {
    loginError.value = '帳號或密碼錯誤'
  } finally {
    loginLoading.value = false
  }
}

function handleLogout() {
  auth.logout()
  cart.value     = []
  remark.value   = ''
  menuData.value = null
}

// ── 顧客 SSE ──────────────────────────────────────
function connectCustomerSSE(token: string) {
  if (sseConn) { sseConn.close(); sseConn = null }
  sseConn = new EventSource(`/customer-order/customer-stream?token=${encodeURIComponent(token)}`)
  sseConn.addEventListener('order_update', (e: MessageEvent) => {
    try {
      const d = JSON.parse(e.data)
      if (Array.isArray(d.orders)) myOrders.value = d.orders
    } catch {}
  })
  sseConn.addEventListener('session_closed', () => {
    sessionClosed.value = true
    localStorage.removeItem('order_session_token')
    sessionToken.value = ''
    if (sseConn) { sseConn.close(); sseConn = null }
  })
}

// ── 菜單 ──────────────────────────────────────────
const loading   = ref(false)
const errorMsg  = ref('')
const menuData  = ref<any>(null)
const menuTitle = ref('點餐')
const activeCat = ref('全部')

const allItems = computed((): any[] => {
  if (!menuData.value) return []
  return (menuData.value.items || []).filter((i: any) => i.status === 1)
})
const allCats = computed((): string[] => {
  const cats = [...new Set(allItems.value.map((i: any) => (i.category || '其他') as string))]
  return ['全部', ...cats]
})
const filteredItems = computed(() =>
  activeCat.value === '全部'
    ? allItems.value
    : allItems.value.filter((i: any) => (i.category || '其他') === activeCat.value)
)

async function loadMenu() {
  const hasAccess = auth.isLoggedIn || qrToken.value || tableFromUrl.value
  if (!hasAccess) return
  loading.value  = true
  errorMsg.value = ''
  const menuId = new URLSearchParams(location.search).get('menu_id') || ''
  try {
    const params: Record<string, string> = {}
    if (qrToken.value) params.t = qrToken.value
    if (menuId)        params.menu_id = menuId
    params._ts = String(Date.now())   // iOS Safari GET 快取防護
    const qs  = new URLSearchParams(params).toString()
    const res = await http.get(`/customer-order/menu${qs ? '?' + qs : ''}`)
    if (!res.data.success) { errorMsg.value = res.data.message || '無法載入菜單'; return }
    menuData.value      = res.data.data
    menuTitle.value     = menuData.value?.name || '點餐'
    resolvedTable.value = res.data.table_no || tableFromUrl.value || ''
    if (res.data.session_token) {
      sessionToken.value = res.data.session_token
      localStorage.setItem('order_session_token', res.data.session_token)
      connectCustomerSSE(res.data.session_token)
    }
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.message || '網路錯誤，請重新整理'
  } finally {
    loading.value = false
  }
}

// ── 購物車 ────────────────────────────────────────
const cart           = ref<CartRow[]>([])
const remark         = ref('')
const submitting     = ref(false)
const orderNo        = ref('')
const showSuccess    = ref(false)
const showCartDrawer = ref(false)   // 手機購物車 drawer

const cartCount    = computed(() => cart.value.reduce((s, r) => s + r.qty, 0))
const cartSubtotal = computed(() => cart.value.reduce((s, r) => s + rowPrice(r) * r.qty, 0))

function commitToCart(item: any, selections: SelectionItem[], qty = 1) {
  const key = selKey(selections)
  const idx = cart.value.findIndex(r => r.item._id === item._id && selKey(r.selections) === key)
  if (idx >= 0) cart.value[idx].qty += qty
  else           cart.value.push({ item, qty, selections })
}

function changeQty(idx: number, delta: number) {
  cart.value[idx].qty += delta
  if (cart.value[idx].qty <= 0) cart.value.splice(idx, 1)
}
function removeFromCart(idx: number) { cart.value.splice(idx, 1) }

async function submitOrder() {
  if (!cart.value.length) return
  submitting.value = true
  try {
    const items = cart.value.map(r => ({
      item_id:        r.item._id,
      item_name:      r.item.name,
      qty:            r.qty,
      price:          rowPrice(r),
      customizations: r.selections.map(s => ({
        group_name:  s.group_name,
        choice_name: s.choice_name,
        extra_price: s.extra_price,
      })),
    }))
    const res = await http.post('/customer-order/', {
      session_token: sessionToken.value || undefined,
      table_no:      resolvedTable.value || auth.username,
      items,
      total:         cartSubtotal.value,
      remark:        remark.value,
      menu_id:       menuData.value?._id,
    })
    orderNo.value      = res.data.order_no || '—'
    showSuccess.value  = true
    showCartDrawer.value = false
  } catch (e: any) {
    appAlert(e?.response?.data?.message || '送出失敗，請重試')
  } finally {
    submitting.value = false
  }
}

function continueOrder() {
  cart.value        = []
  remark.value      = ''
  orderNo.value     = ''
  showSuccess.value = false
}

// ── 客製化（有選項組的品項開抽屜，沒有的直接加入）──────
const customSheet = ref<InstanceType<typeof OrderCustomizeSheet> | null>(null)

function handleItemClick(item: any) {
  if ((item.applied_groups || []).length > 0) customSheet.value?.open(item)
  else commitToCart(item, [])
}

// ── 版面：桌機固定高度+內部滾動 ───────────────────
function applyBodyStyle() {
  if (window.innerWidth >= 768) document.body.style.overflow = 'hidden'
  else                          document.body.style.overflow = ''
}

onMounted(async () => {
  if (auth.isLoggedIn && !auth.username) await auth.fetchMe()
  if (auth.isLoggedIn || tableFromUrl.value || qrToken.value) await loadMenu()
  // loadMenu 會連 SSE；若 sessionToken 已存在（頁面重整）且 SSE 尚未連接，補連
  if (sessionToken.value && !sseConn) connectCustomerSSE(sessionToken.value)
  applyBodyStyle()
  window.addEventListener('resize', applyBodyStyle)
})
onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('resize', applyBodyStyle)
  if (sseConn) { sseConn.close(); sseConn = null }
})
</script>

<template>
  <!-- 桌況已結束 → 全屏感謝頁 -->
  <div v-if="sessionClosed" class="session-ended-screen">
    <div class="session-ended-card">
      <div class="fz-350">🙏</div>
      <h4 class="fw-bold mt-3 mb-2">感謝您的光臨</h4>
      <p class="text-muted mb-1">本次用餐已結束</p>
      <p class="text-muted small">如需再次點餐，請重新掃描桌上的 QR Code</p>
    </div>
  </div>

  <!-- 無參數且未登入 → 空白（防止直接瀏覽） -->
  <template v-else-if="!qrToken && !tableFromUrl && !auth.isLoggedIn"></template>

  <!-- 有 tableFromUrl 但未登入 → 顯示登入遮罩（內部人員用） -->
  <div v-else-if="!sessionClosed && tableFromUrl && (!auth.isLoggedIn || !auth.username)" class="overlay-login">
    <div class="login-card">
      <i class="bi bi-cup-hot text-primary fz-220"></i>
      <h5 class="mt-2 mb-1 fw-bold">點餐系統</h5>
      <p class="text-muted small mb-0">請先登入以繼續點餐</p>
      <form class="mt-4 text-start" @submit.prevent="doLogin">
        <div class="mb-3">
          <input v-model="loginForm.username" type="text" class="form-control"
                 placeholder="帳號" required autocomplete="username" />
        </div>
        <div class="mb-3">
          <input v-model="loginForm.password" type="password" class="form-control"
                 placeholder="密碼" required autocomplete="current-password" />
        </div>
        <div v-if="loginError" class="alert alert-danger py-2 small mb-3">{{ loginError }}</div>
        <button type="submit" class="btn btn-primary w-100 py-2 fw-semibold"
                :disabled="loginLoading">
          <span v-if="loginLoading" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-box-arrow-in-right me-1"></i>登入
        </button>
      </form>
    </div>
  </div>

  <!-- ── 主畫面 ──────────────────────────────────── -->
  <div v-else-if="!sessionClosed" id="order-app">

    <!-- 頂部列 -->
    <div id="order-topbar">
      <h6 class="brand-title mb-0">
        <i class="bi bi-cup-hot me-1 text-primary"></i>{{ menuTitle }}
      </h6>
      <div class="topbar-right">
        <!-- [U13] 原本手機上隱藏（d-none d-sm-inline），但顧客幾乎都用手機，看不到自己的桌號 -->
        <span v-if="resolvedTable || tableFromUrl || auth.username"
              class="table-chip me-2">
          <i class="bi bi-geo-alt me-1"></i>{{ resolvedTable || tableFromUrl || auth.username }}
        </span>
        <button v-if="auth.isLoggedIn" class="btn btn-sm btn-outline-secondary me-1" @click="handleLogout">登出</button>
        <!-- 手機版購物車按鈕 -->
        <button v-if="cartCount > 0" class="btn btn-sm btn-primary d-md-none"
                @click="showCartDrawer = true">
          <i class="bi bi-cart3"></i>
          <span class="ms-1 fw-bold">{{ cartCount }}</span>
        </button>
      </div>
    </div>

    <!-- 分類 tabs -->
    <div id="order-cats">
      <button v-for="cat in allCats" :key="cat"
              class="cat-tab" :class="{ active: activeCat === cat }"
              @click="activeCat = cat">{{ cat }}</button>
    </div>

    <!-- 主體：左品項 ＋ 右購物車（桌機） -->
    <div id="order-body">

      <!-- 品項區 -->
      <div id="panel-items">
        <div v-if="loading" class="text-center py-5 text-muted">
          <div class="spinner-border"></div>
        </div>
        <div v-else-if="errorMsg" class="text-center py-5 text-muted">
          <i class="bi bi-exclamation-circle fs-1 d-block mb-2"></i>{{ errorMsg }}
        </div>
        <div v-else class="item-grid">
          <div v-if="!filteredItems.length" class="text-center py-5 text-muted grid-full">
            <i class="bi bi-inbox fs-2 d-block mb-2"></i>目前無品項
          </div>

          <div v-for="item in filteredItems" :key="item._id"
               class="item-card" @click="handleItemClick(item)">

            <!-- 有圖片 -->
            <template v-if="item.image_url">
              <div class="item-img">
                <img :src="item.image_url" :alt="item.name" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.name }}</div>
                <div v-if="item.description" class="item-desc">{{ item.description }}</div>
                <div class="item-price">NT${{ item.price }}</div>
              </div>
            </template>

            <!-- 無圖片：大字排版 -->
            <template v-else>
              <div class="item-textbody">
                <div class="item-bigname">{{ item.name }}</div>
                <div v-if="item.description" class="item-desc mt-1">{{ item.description }}</div>
                <div class="item-price mt-auto pt-2">NT${{ item.price }}</div>
              </div>
            </template>

            <!-- 客製化標記 -->
            <div v-if="item.applied_groups?.length" class="cust-badge">
              <i class="bi bi-sliders2"></i>
            </div>
          </div>
        </div>
      </div><!-- /panel-items -->

      <!-- 購物車面板（桌機） -->
      <div id="panel-cart">
        <div class="cart-title">
          <i class="bi bi-cart3 me-1"></i>購物車
          <span v-if="cartCount" class="cart-badge">{{ cartCount }}</span>
        </div>

        <div v-if="!cart.length" class="cart-empty">
          <i class="bi bi-cart-x fs-2 d-block mb-2 text-muted"></i>
          <span class="text-muted small">尚未加入品項</span>
        </div>

        <div v-else class="cart-rows">
          <OrderCartRows :cart="cart" @change-qty="changeQty" @remove="removeFromCart" />
        </div>

        <div v-if="cart.length" class="cart-footer">
          <div class="cf-total">
            <span>合計</span>
            <span class="text-primary fw-bold">NT${{ cartSubtotal }}</span>
          </div>
          <textarea v-model="remark" class="form-control form-control-sm mt-2"
                    rows="2" placeholder="備註（選填）"></textarea>
          <button class="btn btn-primary w-100 mt-2 py-2 fw-semibold"
                  :disabled="submitting || !cart.length" @click="submitOrder">
            <span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-check-circle me-1"></i>送出訂單
          </button>
        </div>

        <!-- 訂單狀態（SSE 即時更新） -->
        <MyOrdersList :orders="myOrders" />
      </div><!-- /panel-cart -->

    </div><!-- /order-body -->

    <!-- 手機版浮動購物車列 -->
    <div v-if="cartCount > 0" id="mobile-cart-bar">
      <button class="btn btn-primary rounded-pill px-4 py-2 fw-semibold shadow"
              @click="showCartDrawer = true">
        <i class="bi bi-cart3 me-1"></i>
        {{ cartCount }} 項 · NT${{ cartSubtotal }}
        <span class="ms-2">查看購物車 →</span>
      </button>
    </div>

  </div><!-- /order-app -->

  <!-- ── 手機購物車 Drawer ─────────────────────── -->
  <OrderBottomSheet :show="showCartDrawer" @close="showCartDrawer = false">
    <template #header>
      <span class="fw-bold"><i class="bi bi-cart3 me-1"></i>購物車</span>
    </template>
    <OrderCartRows :cart="cart" @change-qty="changeQty" @remove="removeFromCart" />
    <div class="cf-total mt-3">
      <span>合計</span>
      <span class="text-primary fw-bold">NT${{ cartSubtotal }}</span>
    </div>
    <textarea v-model="remark" class="form-control form-control-sm mt-2"
              rows="2" placeholder="備註（選填）"></textarea>
    <button class="btn btn-primary w-100 mt-3 py-2 fw-semibold"
            :disabled="submitting" @click="submitOrder">
      <span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>
      <i v-else class="bi bi-check-circle me-1"></i>送出訂單
    </button>

    <!-- 訂單狀態（SSE 即時更新） -->
    <MyOrdersList :orders="myOrders" class="mt-3" />
  </OrderBottomSheet>

  <!-- ── 客製化 ─────────────────────────────── -->
  <OrderCustomizeSheet ref="customSheet" @add="commitToCart" />

  <!-- ── 送出成功 Modal ───────────────────────── -->
  <Teleport to="body">
    <div v-if="showSuccess" class="center-mask">
      <div class="success-card">
        <div class="fz-300">🎉</div>
        <h5 class="fw-bold mt-2 mb-1">訂單已送出！</h5>
        <p class="text-muted small mb-1">訂單編號</p>
        <h4 class="text-primary fw-bold mb-3">{{ orderNo }}</h4>
        <p class="text-muted small">請稍候，我們將盡快為您備餐。</p>
        <button class="btn btn-primary mt-2 px-4" @click="continueOrder">
          <i class="bi bi-plus-circle me-1"></i>繼續點餐
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── 登入遮罩 ─────────────────────────────────── */
.overlay-login {
  min-height: 100vh;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.login-card {
  background: #fff;
  border-radius: 1rem;
  padding: 2rem;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 4px 24px rgba(0,0,0,.1);
  text-align: center;
}

/* ── 整體 app ─────────────────────────────────── */
#order-app {
  background: #f8fafc;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── 頂部列 ───────────────────────────────────── */
#order-topbar {
  position: sticky;
  top: 0;
  /* [U13] 固定高度：分類列以 top: 49px 黏在頂列下方，頂列實際只有約 40px 時中間會露出捲動中的品項 */
  min-height: 49px;
  box-sizing: border-box;
  z-index: 50;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  padding: .65rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.brand-title { font-size: .95rem; font-weight: 700; }
.topbar-right { display: flex; align-items: center; }
.table-chip {
  font-size: .8rem; font-weight: 600; color: #475569;
  background: #f1f5f9; border-radius: 999px; padding: 3px 10px; white-space: nowrap;
}

/* ── 分類 tabs ────────────────────────────────── */
#order-cats {
  position: sticky;
  top: 49px;
  z-index: 40;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  overflow-x: auto;
  scrollbar-width: none;
  flex-shrink: 0;
}
#order-cats::-webkit-scrollbar { display: none; }
.cat-tab {
  flex-shrink: 0;
  padding: .5rem 1rem;
  font-size: .85rem;
  font-weight: 600;
  border: none;
  background: none;
  color: #64748b;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
}
.cat-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; }

/* ── 主體 ─────────────────────────────────────── */
#order-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
#panel-items {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

/* ── 品項格子 ─────────────────────────────────── */
.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: .75rem;
  padding: 1rem;
}

.item-card {
  background: #fff;
  border-radius: .75rem;
  overflow: hidden;
  box-shadow: 0 1px 5px rgba(0,0,0,.08);
  cursor: pointer;
  position: relative;
  transition: transform .1s, box-shadow .1s;
  display: flex;
  flex-direction: column;
}
.item-card:active { transform: scale(.97); }
.item-card:hover  { box-shadow: 0 3px 12px rgba(59,130,246,.18); }

/* 有圖片版 */
.item-img { width: 100%; aspect-ratio: 4/3; overflow: hidden; }
.item-img img { width: 100%; height: 100%; object-fit: cover; }
.item-info {
  padding: .55rem .75rem;
  display: flex;
  flex-direction: column;
  gap: .1rem;
}

/* 無圖片：大字排版 */
.item-textbody {
  padding: .9rem .75rem .75rem;
  display: flex;
  flex-direction: column;
  min-height: 100px;
  flex: 1;
}
.item-bigname {
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.35;
  color: #1e293b;
}

.item-name  { font-weight: 600; font-size: .88rem; color: #1e293b; }
.item-desc  { font-size: .72rem; color: #94a3b8; }
.item-price { color: #3b82f6; font-weight: 700; font-size: .92rem; }

/* 客製化標記角標 */
.cust-badge {
  position: absolute;
  top: .35rem;
  right: .35rem;
  background: rgba(59,130,246,.15);
  color: #3b82f6;
  border-radius: 50%;
  width: 1.4rem;
  height: 1.4rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: .7rem;
}

/* ── 桌機購物車面板 ────────────────────────────── */
#panel-cart {
  display: none;   /* 手機隱藏，桌機顯示 */
  flex-direction: column;
  width: 300px;
  min-width: 300px;
  background: #fff;
  border-left: 1px solid #e2e8f0;
  padding: 1rem;
  overflow-y: auto;
}
.cart-title {
  font-weight: 700;
  font-size: .95rem;
  display: flex;
  align-items: center;
  padding-bottom: .75rem;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}
.cart-badge {
  margin-left: .35rem;
  background: #3b82f6;
  color: #fff;
  border-radius: 50%;
  width: 1.3rem;
  height: 1.3rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: .68rem;
  font-weight: 700;
}
.cart-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.cart-rows { flex: 1; overflow-y: auto; }
.cart-footer { flex-shrink: 0; margin-top: auto; padding-top: .5rem; }

/* ── 手機浮動列 ────────────────────────────────── */
#mobile-cart-bar {
  position: fixed;
  bottom: calc(1.25rem + env(safe-area-inset-bottom));   /* [MOBILE] 避開 iPhone 底部橫條 */
  left: 50%;
  transform: translateX(-50%);
  z-index: 60;
}

.cf-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: .9rem;
  padding: .5rem 0;
  border-top: 1px solid #e2e8f0;
}

/* ── 成功 Modal（置中） ─────────────────────────── */
.center-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.5);
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.success-card {
  background: #fff;
  border-radius: 1rem;
  padding: 2rem 1.5rem;
  text-align: center;
  max-width: 340px;
  width: 100%;
  box-shadow: 0 8px 40px rgba(0,0,0,.12);
}

/* ── 桌況結束全屏 ─────────────────────────────── */
.session-ended-screen {
  position: fixed;
  inset: 0;
  background: #f8fafc;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.session-ended-card {
  text-align: center;
  max-width: 320px;
}

/* ── 桌機：固定高度內部滾動 ────────────────────── */
@media (min-width: 768px) {
  #order-app { height: 100vh; overflow: hidden; }
  #order-topbar, #order-cats { position: static; }
  #order-body { height: 1px; flex: 1; } /* flex: 1 負責撐高，height: 1px 讓 overflow hidden 生效 */
  #panel-cart { display: flex; }
  #mobile-cart-bar { display: none !important; }
}

/* ── [MOBILE] 觸控裝置：輸入框 16px 防 iOS 聚焦放大（購物車加減鈕見 OrderCartRows.vue）── */
@media (pointer: coarse) {
  textarea.form-control, input.form-control { font-size: 16px; }
}
</style>
