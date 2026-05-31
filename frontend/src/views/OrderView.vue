<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import http from '@/api'

const auth  = useAuthStore()
const route = useRoute()

// QR 碼帶入的桌號（不需登入）
const tableFromUrl = computed(() => ((route.query.table as string) || '').trim())

// ── Types ─────────────────────────────────────────
interface SelectionItem {
  group_id:    string
  group_name:  string
  choice_id:   string
  choice_name: string
  extra_price: number
}
interface CartRow {
  item:       any
  qty:        number
  selections: SelectionItem[]
}

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
  cart.value    = []
  remark.value  = ''
  menuData.value = null
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
  if (!auth.isLoggedIn && !tableFromUrl.value) return
  loading.value  = true
  errorMsg.value = ''
  const menuId   = new URLSearchParams(location.search).get('menu_id') || ''
  try {
    const res = await http.get(`/customer-order/menu${menuId ? `?menu_id=${menuId}` : ''}`)
    if (!res.data.success) { errorMsg.value = res.data.message || '無法載入菜單'; return }
    menuData.value  = res.data.data
    menuTitle.value = menuData.value?.name || '點餐'
  } catch {
    errorMsg.value = '網路錯誤，請重新整理'
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

function selKey(sel: SelectionItem[]) {
  return sel.map(s => `${s.group_id}:${s.choice_id}`).sort().join('|')
}

function rowPrice(row: CartRow): number {
  return (row.item.price || 0) + row.selections.reduce((s, x) => s + (x.extra_price || 0), 0)
}

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
      table_no: tableFromUrl.value || auth.username,
      items,
      total:   cartSubtotal.value,
      note:    remark.value,
      menu_id: menuData.value?._id,
    })
    orderNo.value      = res.data.order_no || '—'
    showSuccess.value  = true
    showCartDrawer.value = false
  } catch (e: any) {
    alert(e?.response?.data?.message || '送出失敗，請重試')
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

// ── 客製化 Modal ──────────────────────────────────
const showCustomModal  = ref(false)
const customTarget     = ref<any>(null)
const customSelections = ref<Record<string, string[]>>({})
const custQty          = ref(1)

const custTotalPrice = computed(() => {
  if (!customTarget.value) return 0
  const groups: any[] = customTarget.value.applied_groups || []
  let extra = 0
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const ch = (grp.choices || []).find((c: any) => c._id === cid)
      if (ch) extra += ch.extra_price || 0
    }
  }
  return (customTarget.value.price + extra) * custQty.value
})

function handleItemClick(item: any) {
  const groups: any[] = item.applied_groups || []
  if (groups.length > 0) {
    custQty.value      = 1
    customTarget.value = item
    // 初始化：預選 is_default
    const sel: Record<string, string[]> = {}
    for (const grp of groups) {
      if (grp.type === 'single') {
        const def = (grp.choices || []).find((c: any) => c.is_default)
        sel[grp._id] = def ? [def._id] : []
      } else {
        sel[grp._id] = (grp.choices || []).filter((c: any) => c.is_default).map((c: any) => c._id)
      }
    }
    customSelections.value = sel
    showCustomModal.value  = true
  } else {
    commitToCart(item, [])
  }
}

function toggleMultiChoice(groupId: string, choiceId: string) {
  const arr = customSelections.value[groupId] || []
  const i   = arr.indexOf(choiceId)
  customSelections.value[groupId] = i >= 0
    ? arr.filter(id => id !== choiceId)
    : [...arr, choiceId]
}

function confirmCustom() {
  const groups: any[] = customTarget.value?.applied_groups || []
  for (const grp of groups) {
    if (grp.required && !(customSelections.value[grp._id]?.length)) {
      alert(`請選擇「${grp.name}」`)
      return
    }
  }
  const selections: SelectionItem[] = []
  for (const grp of groups) {
    for (const cid of (customSelections.value[grp._id] || [])) {
      const ch = (grp.choices || []).find((c: any) => c._id === cid)
      if (ch) {
        selections.push({
          group_id:    grp._id,
          group_name:  grp.name,
          choice_id:   cid,
          choice_name: ch.name,
          extra_price: ch.extra_price || 0,
        })
      }
    }
  }
  commitToCart(customTarget.value, selections, custQty.value)
  showCustomModal.value = false
}

// ── 版面：桌機固定高度+內部滾動 ───────────────────
function applyBodyStyle() {
  if (window.innerWidth >= 768) document.body.style.overflow = 'hidden'
  else                          document.body.style.overflow = ''
}

onMounted(async () => {
  if (auth.isLoggedIn && !auth.username) await auth.fetchMe()
  if (auth.isLoggedIn || tableFromUrl.value) await loadMenu()
  applyBodyStyle()
  window.addEventListener('resize', applyBodyStyle)
})
onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('resize', applyBodyStyle)
})
</script>

<template>
  <!-- ── 登入遮罩（QR 掃碼帶桌號時跳過） ─────────── -->
  <div v-if="!tableFromUrl && (!auth.isLoggedIn || !auth.username)" class="overlay-login">
    <div class="login-card">
      <i class="bi bi-cup-hot text-primary" style="font-size:2.2rem"></i>
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
  <div v-else id="order-app">

    <!-- 頂部列 -->
    <div id="order-topbar">
      <h6 class="brand-title mb-0">
        <i class="bi bi-cup-hot me-1 text-primary"></i>{{ menuTitle }}
      </h6>
      <div class="topbar-right">
        <span class="text-muted small me-2 d-none d-sm-inline">
          <i class="bi bi-geo-alt me-1"></i>{{ tableFromUrl || auth.username }}
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
          <div v-if="!filteredItems.length" class="text-center py-5 text-muted"
               style="grid-column:1/-1">
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
          <div v-for="(row, idx) in cart" :key="idx" class="cart-row">
            <div class="cr-info">
              <div class="cr-name">{{ row.item.name }}</div>
              <div v-if="row.selections.length" class="cr-opts">
                {{ row.selections.map(s => s.choice_name).join(' · ') }}
              </div>
              <div class="cr-price">NT${{ rowPrice(row) }}</div>
            </div>
            <div class="cr-qty">
              <button @click="changeQty(idx, -1)">－</button>
              <span>{{ row.qty }}</span>
              <button @click="changeQty(idx, 1)">＋</button>
            </div>
            <button class="cr-del" @click="removeFromCart(idx)">
              <i class="bi bi-x"></i>
            </button>
          </div>
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
  <Teleport to="body">
    <div v-if="showCartDrawer" class="bottom-mask" @click.self="showCartDrawer = false">
      <div class="bottom-sheet">
        <div class="bs-header">
          <span class="fw-bold"><i class="bi bi-cart3 me-1"></i>購物車</span>
          <button class="btn-close" @click="showCartDrawer = false"></button>
        </div>
        <div class="bs-body">
          <div v-for="(row, idx) in cart" :key="idx" class="cart-row">
            <div class="cr-info">
              <div class="cr-name">{{ row.item.name }}</div>
              <div v-if="row.selections.length" class="cr-opts">
                {{ row.selections.map(s => s.choice_name).join(' · ') }}
              </div>
              <div class="cr-price">NT${{ rowPrice(row) }}</div>
            </div>
            <div class="cr-qty">
              <button @click="changeQty(idx, -1)">－</button>
              <span>{{ row.qty }}</span>
              <button @click="changeQty(idx, 1)">＋</button>
            </div>
            <button class="cr-del" @click="removeFromCart(idx)">
              <i class="bi bi-x"></i>
            </button>
          </div>
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
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── 客製化 Modal ─────────────────────────── -->
  <Teleport to="body">
    <div v-if="showCustomModal" class="bottom-mask" @click.self="showCustomModal = false">
      <div class="bottom-sheet">
        <div class="bs-header">
          <div>
            <div class="fw-bold">{{ customTarget?.name }}</div>
            <div class="text-primary small">NT${{ customTarget?.price }}</div>
          </div>
          <button class="btn-close" @click="showCustomModal = false"></button>
        </div>

        <div class="bs-body" v-if="customTarget">
          <div v-for="grp in customTarget.applied_groups" :key="grp._id" class="og-section">
            <div class="og-title">
              {{ grp.name }}
              <span v-if="grp.required" class="badge bg-danger ms-1 og-badge">必選</span>
              <span v-if="grp.type === 'multiple'" class="badge bg-secondary ms-1 og-badge">可複選</span>
            </div>
            <div class="og-choices">
              <div v-for="ch in grp.choices" :key="ch._id"
                   class="choice-pill"
                   :class="{ active: customSelections[grp._id]?.includes(ch._id) }"
                   @click="grp.type === 'single'
                             ? (customSelections[grp._id] = [ch._id])
                             : toggleMultiChoice(grp._id, ch._id)">
                {{ ch.name }}
                <span v-if="ch.extra_price > 0" class="choice-extra">+{{ ch.extra_price }}</span>
              </div>
            </div>
          </div>
          <div v-if="!customTarget.applied_groups?.length"
               class="text-center text-muted small py-3">無客製選項</div>
        </div>

        <div class="bs-footer">
          <div class="qty-ctrl">
            <button @click="custQty > 1 && custQty--">－</button>
            <span>{{ custQty }}</span>
            <button @click="custQty++">＋</button>
          </div>
          <div class="cust-total-lbl">NT${{ custTotalPrice }}</div>
          <button class="btn btn-primary fw-semibold px-3" @click="confirmCustom">
            <i class="bi bi-cart-plus me-1"></i>加入
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── 送出成功 Modal ───────────────────────── -->
  <Teleport to="body">
    <div v-if="showSuccess" class="center-mask">
      <div class="success-card">
        <div style="font-size:3rem">🎉</div>
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
  bottom: 1.25rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 60;
}

/* ── 共用 Cart Row ─────────────────────────────── */
.cart-row {
  display: flex;
  align-items: center;
  gap: .4rem;
  padding: .5rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.cr-info  { flex: 1; min-width: 0; }
.cr-name  { font-weight: 600; font-size: .85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cr-opts  { font-size: .7rem; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cr-price { font-size: .78rem; color: #3b82f6; font-weight: 600; }
.cr-qty   { display: flex; align-items: center; gap: .2rem; flex-shrink: 0; }
.cr-qty button {
  width: 1.5rem; height: 1.5rem;
  border: 1px solid #e2e8f0; border-radius: 4px;
  background: #f8fafc; font-size: .85rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.cr-qty span { font-weight: 700; font-size: .82rem; min-width: 1.2rem; text-align: center; }
.cr-del {
  background: none; border: none; color: #94a3b8;
  cursor: pointer; font-size: 1.1rem; padding: .1rem; line-height: 1;
  flex-shrink: 0;
}
.cr-del:hover { color: #ef4444; }
.cf-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: .9rem;
  padding: .5rem 0;
  border-top: 1px solid #e2e8f0;
}

/* ── Bottom Sheet（購物車 drawer + 客製化 modal） ── */
.bottom-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.5);
  z-index: 1050;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.bottom-sheet {
  background: #fff;
  border-radius: 16px 16px 0 0;
  width: 100%;
  max-width: 480px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
}
.bs-header {
  padding: 1rem 1rem .75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.bs-body {
  padding: .75rem 1rem;
  overflow-y: auto;
  flex: 1;
}
.bs-footer {
  padding: .75rem 1rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: .75rem;
  flex-shrink: 0;
}

/* ── 客製化選項 ────────────────────────────────── */
.og-section   { margin-bottom: 1.1rem; }
.og-title     { font-weight: 700; font-size: .88rem; margin-bottom: .5rem; }
.og-badge     { font-size: .6rem !important; }
.og-choices   { display: flex; flex-wrap: wrap; gap: .4rem; }
.choice-pill  {
  padding: .35rem .8rem;
  border-radius: 20px;
  border: 1.5px solid #e2e8f0;
  font-size: .82rem;
  cursor: pointer;
  user-select: none;
  transition: all .15s;
  background: #f8fafc;
}
.choice-pill.active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.choice-extra { font-size: .7rem; color: #3b82f6; margin-left: .2rem; }

.qty-ctrl { display: flex; align-items: center; gap: .35rem; }
.qty-ctrl button {
  width: 2rem; height: 2rem;
  border: 1.5px solid #e2e8f0; border-radius: 8px;
  background: #f8fafc; font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.qty-ctrl span { font-size: 1rem; font-weight: 700; min-width: 1.5rem; text-align: center; }
.cust-total-lbl { flex: 1; text-align: right; font-weight: 700; font-size: 1rem; color: #3b82f6; }

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

/* ── 桌機：固定高度內部滾動 ────────────────────── */
@media (min-width: 768px) {
  #order-app { height: 100vh; overflow: hidden; }
  #order-topbar, #order-cats { position: static; }
  #order-body { height: 1px; flex: 1; } /* flex: 1 負責撐高，height: 1px 讓 overflow hidden 生效 */
  #panel-cart { display: flex; }
  #mobile-cart-bar { display: none !important; }
}
</style>
