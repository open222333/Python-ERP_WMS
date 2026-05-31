<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate, ROLE_COLOR, ROLE_LABEL } from '@/utils/format'
import type { User, UserTemplate } from '@/types'

const toast = useToastStore()

// ── State ────────────────────────────────────────────────
const activeTab  = ref<'users' | 'templates'>('users')
const loading    = ref(false)
const saving     = ref(false)

const users     = ref<User[]>([])
const templates = ref<UserTemplate[]>([])

// ── User modal ───────────────────────────────────────────
const showUserModal = ref(false)
const userForm = ref({
  _id: '',
  username: '',
  password: '',
  template_id: '',
})
const selectedTemplateMeta = computed(() => {
  if (!userForm.value.template_id) return null
  return templates.value.find(t => t._id === userForm.value.template_id) || null
})

// ── Template modal ───────────────────────────────────────
const showTplModal = ref(false)
const tplForm = ref({
  _id: '',
  name: '',
  role: 'operator' as 'admin' | 'operator' | 'viewer',
  description: '',
  is_system: false,
  pages_enabled: {} as Record<string, boolean>,
})

// ── Nav pages definition ─────────────────────────────────
interface NavPage { key: string; label: string; group: string; system?: boolean }
const NAV_PAGES: NavPage[] = [
  { key: 'cust-orders',       label: '訂單管理',   group: '顧客點單' },
  { key: 'kitchen-link',      label: '備餐顯示',   group: '顧客點單' },
  { key: 'order-link',        label: '顧客點單頁', group: '顧客點單' },
  { key: 'qr-codes',          label: 'QR 碼管理',  group: '顧客點單' },
  { key: 'categories',        label: '產品分類',   group: '商品管理' },
  { key: 'products',          label: '產品資料',   group: '商品管理' },
  { key: 'warehouses',        label: '倉庫管理',   group: '倉儲管理' },
  { key: 'inventory',         label: '庫存查詢',   group: '倉儲管理' },
  { key: 'inbound',           label: '入庫管理',   group: '出入庫' },
  { key: 'outbound',          label: '出庫管理',   group: '出入庫' },
  { key: 'movements',         label: '庫存移動',   group: '出入庫' },
  { key: 'quick-io',          label: '快速出入庫', group: '出入庫' },
  { key: 'pos-sales',         label: '銷售記錄',   group: '財務' },
  { key: 'pos-report',        label: '銷售報表',   group: '財務' },
  { key: 'menus',             label: '菜單管理',   group: 'POS 收銀' },
  { key: 'pos-link',          label: '開啟收銀台', group: 'POS 收銀' },
  { key: 'delivery-orders',   label: '外送訂單',   group: '外送平台' },
  { key: 'delivery-settings', label: '平台設定',   group: '外送平台' },
  { key: 'invoices',          label: '電子發票',   group: '財務' },
  { key: 'invoice-settings',  label: '發票設定',   group: '財務' },
  { key: 'users',    label: '使用者管理', group: '系統', system: true },
  { key: 'logs',     label: '操作紀錄',   group: '系統', system: true },
  { key: 'settings', label: '系統設定',   group: '系統' },
]

const pageGroups = computed(() => {
  const map: Record<string, NavPage[]> = {}
  for (const p of NAV_PAGES) {
    if (!map[p.group]) map[p.group] = []
    map[p.group].push(p)
  }
  return Object.entries(map)
})

// ── Template map (id → name) ─────────────────────────────
const tplMap = computed(() => Object.fromEntries(templates.value.map(t => [t._id, t])))

// ── User count per template ──────────────────────────────
const tplUsageMap = computed(() => {
  const m: Record<string, number> = {}
  for (const u of users.value) {
    if (u.template_id) m[u.template_id] = (m[u.template_id] || 0) + 1
  }
  return m
})

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [uRes, tRes] = await Promise.all([
      http.get('/user/'),
      http.get('/user/templates/'),
    ])
    users.value     = uRes.data?.data || []
    templates.value = tRes.data?.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── User CRUD ────────────────────────────────────────────
function openUserModal(u?: User) {
  userForm.value = {
    _id:         u?._id         || '',
    username:    u?.username    || '',
    password:    '',
    template_id: u?.template_id || '',
  }
  showUserModal.value = true
}

async function saveUser() {
  const f = userForm.value
  if (!f._id && !f.username.trim()) { toast.show('帳號不得為空', 'danger'); return }
  if (!f._id && !f.password)        { toast.show('新帳號需設定密碼', 'danger'); return }
  if (!f._id && !f.template_id)     { toast.show('請選擇使用者模板', 'danger'); return }
  saving.value = true
  try {
    if (f._id) {
      const body: Record<string, unknown> = { template_id: f.template_id || null }
      if (f.password) body.password = f.password
      await http.put(`/user/${f._id}`, body)
    } else {
      await http.post('/user/', {
        username:    f.username.trim(),
        password:    f.password,
        template_id: f.template_id,
      })
    }
    toast.show('儲存成功')
    showUserModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteUser(id: string, uname: string) {
  if (!confirm(`確定刪除使用者 ${uname}？`)) return
  try {
    await http.delete(`/user/${id}`)
    toast.show('已刪除')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── Template CRUD ────────────────────────────────────────
function openTplModal(t?: UserTemplate) {
  if (t) {
    tplForm.value = {
      _id:           t._id,
      name:          t.name,
      role:          t.role,
      description:   t.description || '',
      is_system:     !!t.is_system,
      pages_enabled: { ...(t.pages_enabled || {}) },
    }
  } else {
    // 新增模板：系統頁面（users/logs）預設依角色決定
    // admin → 開啟；其餘 → 關閉（由角色選擇後可調整）
    const defaultRole = 'operator'
    const pages: Record<string, boolean> = {}
    NAV_PAGES.forEach(p => {
      pages[p.key] = p.system ? defaultRole === 'admin' : true
    })
    tplForm.value = {
      _id:           '',
      name:          '',
      role:          defaultRole,
      description:   '',
      is_system:     false,
      pages_enabled: pages,
    }
  }
  showTplModal.value = true
}

async function saveTpl() {
  const f = tplForm.value
  if (!f.name.trim()) { toast.show('模板名稱不得為空', 'danger'); return }
  saving.value = true
  try {
    // Collect pages：admin 角色強制開啟系統頁面；其餘角色可自由配置系統頁面
    const pages: Record<string, boolean> = {}
    NAV_PAGES.forEach(p => {
      if (p.system && f.role === 'admin') {
        pages[p.key] = true   // admin 模板：系統頁面強制開啟
      } else {
        pages[p.key] = f.pages_enabled[p.key] !== false
      }
    })

    const body = f.is_system
      ? { pages_enabled: pages }
      : { name: f.name.trim(), role: f.role, description: f.description, pages_enabled: pages }

    let res: any
    if (f._id) {
      res = await http.put(`/user/templates/${f._id}`, body)
    } else {
      res = await http.post('/user/templates/', body)
    }

    const synced = res.data?.synced_users
    const msg = f._id
      ? `模板已更新${synced ? `（已同步 ${synced} 個使用者角色）` : ''}`
      : '模板已建立'
    toast.show(msg)
    showTplModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteTpl(id: string, name: string) {
  if (!confirm(`確定刪除使用者模板「${name}」？\n已指派此模板的使用者角色與頁面設定將不再受此模板控制。`)) return
  try {
    await http.delete(`/user/templates/${id}`)
    toast.show('模板已刪除')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

onMounted(load)
</script>

<template>
  <!-- ── Tabs ─────────────────────────────────────────── -->
  <ul class="nav nav-tabs mb-3">
    <li class="nav-item">
      <a
        class="nav-link"
        :class="{ active: activeTab === 'users' }"
        href="#"
        @click.prevent="activeTab = 'users'"
      >
        <i class="bi bi-people me-1"></i>使用者
      </a>
    </li>
    <li class="nav-item">
      <a
        class="nav-link"
        :class="{ active: activeTab === 'templates' }"
        href="#"
        @click.prevent="activeTab = 'templates'"
      >
        <i class="bi bi-person-badge me-1"></i>使用者模板
      </a>
    </li>
  </ul>

  <!-- ── Users Tab ─────────────────────────────────────── -->
  <div v-if="activeTab === 'users'" class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-people me-1"></i>使用者列表</h6>
      <button class="btn btn-sm btn-primary" @click="openUserModal()">
        <i class="bi bi-person-plus"></i> 新增使用者
      </button>
    </div>
    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr><th>帳號</th><th>角色</th><th>使用者模板</th><th>建立時間</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!users.length">
            <td colspan="5" class="text-center text-muted py-3">無使用者</td>
          </tr>
          <tr v-for="u in users" :key="u._id">
            <td>
              <i class="bi bi-person-circle me-1 text-muted"></i>
              <strong>{{ u.username }}</strong>
            </td>
            <td>
              <span class="badge" :class="`bg-${ROLE_COLOR[u.role] || 'secondary'}`">{{ u.role }}</span>
            </td>
            <td>
              <span v-if="u.template_id && tplMap[u.template_id]" class="badge bg-info text-dark">
                {{ tplMap[u.template_id].name }}
              </span>
              <span v-else class="text-muted small">—</span>
            </td>
            <td class="text-muted small">{{ fmtDate(u.created_at) }}</td>
            <td>
              <button class="btn btn-sm btn-outline-primary me-1" @click="openUserModal(u)">
                <i class="bi bi-pencil"></i>
              </button>
              <button
                v-if="u.username === 'admin'"
                class="btn btn-sm btn-outline-secondary"
                disabled
                title="系統管理員帳號不可刪除"
              >
                <i class="bi bi-lock-fill"></i>
              </button>
              <button
                v-else
                class="btn btn-sm btn-outline-danger"
                @click="deleteUser(u._id, u.username)"
              >
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Templates Tab ─────────────────────────────────── -->
  <div v-else class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-person-badge me-1"></i>使用者模板</h6>
      <button class="btn btn-sm btn-primary" @click="openTplModal()">
        <i class="bi bi-plus-lg"></i> 新增使用者模板
      </button>
    </div>
    <div class="px-3 pt-3 pb-1 text-muted small">
      每個模板定義對應的系統角色與頁面顯示設定，指派給使用者後決定其權限及側欄可見頁面。
      <span class="badge bg-warning text-dark ms-1"><i class="bi bi-lock-fill"></i> 系統</span>
      標記的模板為預設模板，不可刪除。
    </div>
    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr><th>模板名稱</th><th>角色</th><th>說明</th><th>已指派使用者</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="!templates.length">
            <td colspan="5" class="text-center text-muted py-3">尚無使用者模板</td>
          </tr>
          <tr v-for="t in templates" :key="t._id">
            <td>
              <strong>{{ t.name }}</strong>
              <span v-if="t.is_system" class="badge bg-warning text-dark ms-1">
                <i class="bi bi-lock-fill"></i> 系統
              </span>
            </td>
            <td>
              <span class="badge" :class="`bg-${ROLE_COLOR[t.role] || 'secondary'}`">
                {{ t.role }}
              </span>
            </td>
            <td class="text-muted small">{{ t.description || '—' }}</td>
            <td class="text-center">{{ tplUsageMap[t._id] || 0 }}</td>
            <td>
              <button class="btn btn-sm btn-outline-primary me-1" @click="openTplModal(t)">
                <i class="bi bi-pencil"></i>
              </button>
              <button
                v-if="!t.is_system"
                class="btn btn-sm btn-outline-danger"
                @click="deleteTpl(t._id, t.name)"
              >
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ══════════ User Modal ══════════ -->
  <Teleport to="body">
    <div
      v-if="showUserModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.45)"
      @click.self="showUserModal = false"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">使用者帳號</h5>
            <button type="button" class="btn-close" @click="showUserModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">
                帳號
                <span v-if="!userForm._id" class="text-danger">*</span>
              </label>
              <input
                v-model="userForm.username"
                type="text"
                class="form-control"
                :disabled="!!userForm._id"
              />
            </div>
            <div class="mb-3">
              <label class="form-label">
                密碼
                <span v-if="!userForm._id" class="text-danger">*</span>
                <span v-else class="text-muted small ms-1">（留空表示不更改）</span>
              </label>
              <input v-model="userForm.password" type="password" class="form-control" placeholder="••••••••" />
            </div>
            <div class="mb-3">
              <label class="form-label">
                使用者模板
                <span v-if="!userForm._id" class="text-danger">*</span>
                <span class="text-muted small ms-1">（決定角色權限與頁面顯示）</span>
              </label>
              <select v-model="userForm.template_id" class="form-select">
                <option value="">— 不指派 —</option>
                <option v-for="t in templates" :key="t._id" :value="t._id">
                  {{ t.name }}（{{ t.role }}）{{ t.is_system ? ' 🔒' : '' }}
                </option>
              </select>
              <div class="form-text d-flex align-items-center gap-1 mt-1">
                對應角色：
                <span
                  class="badge"
                  :class="selectedTemplateMeta ? `bg-${ROLE_COLOR[selectedTemplateMeta.role]}` : 'bg-secondary'"
                >
                  {{ selectedTemplateMeta ? ROLE_LABEL[selectedTemplateMeta.role] : '—' }}
                </span>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showUserModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveUser">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ══════════ Template Modal ══════════ -->
  <Teleport to="body">
    <div
      v-if="showTplModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.45)"
      @click.self="showTplModal = false"
    >
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ tplForm._id ? '編輯使用者模板' : '新增使用者模板' }}</h5>
            <button type="button" class="btn-close" @click="showTplModal = false"></button>
          </div>
          <div class="modal-body">
            <!-- System template notice -->
            <div v-if="tplForm.is_system" class="alert alert-warning py-2 small mb-3">
              <i class="bi bi-lock-fill me-1"></i>
              系統預設模板：名稱與角色不可修改，但可調整頁面顯示設定。
            </div>

            <div class="mb-3">
              <label class="form-label">模板名稱 <span class="text-danger">*</span></label>
              <input
                v-model="tplForm.name"
                type="text"
                class="form-control"
                :disabled="tplForm.is_system"
                placeholder="例：收銀員、倉管人員"
              />
            </div>
            <div class="mb-3">
              <label class="form-label">對應角色 <span class="text-danger">*</span></label>
              <select v-model="tplForm.role" class="form-select" :disabled="tplForm.is_system">
                <option value="viewer">Viewer（唯讀）</option>
                <option value="operator">Operator（操作員）</option>
                <option value="admin">Admin（管理員）</option>
              </select>
              <div class="form-text">
                指派此模板的使用者將自動獲得對應的系統角色。若更新角色，已指派此模板的帳號也會同步更新。
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label">說明</label>
              <input
                v-model="tplForm.description"
                type="text"
                class="form-control"
                placeholder="選填，簡短描述此模板用途"
              />
            </div>

            <hr />
            <div class="mb-2 fw-semibold">頁面顯示設定</div>
            <p class="text-muted small mb-3">
              勾選此模板的使用者可在後台側欄看到哪些功能頁面。未勾選的頁面將會隱藏。
            </p>

            <div class="row g-2">
              <template v-for="[group, pages] in pageGroups" :key="group">
                <div class="col-12">
                  <div
                    class="text-muted small fw-semibold mb-1"
                    style="font-size:.72rem; letter-spacing:.05em; text-transform:uppercase"
                  >
                    {{ group }}
                  </div>
                  <div class="d-flex flex-wrap gap-2 mb-1">
                    <div
                      v-for="p in pages"
                      :key="p.key"
                      class="form-check form-check-inline"
                      :title="p.system && tplForm.role === 'admin' ? '系統頁面，Admin 模板固定開啟' : ''"
                    >
                      <input
                        :id="`tpl-chk-${p.key}`"
                        class="form-check-input"
                        type="checkbox"
                        :checked="(p.system && tplForm.role === 'admin') ? true : tplForm.pages_enabled[p.key] !== false"
                        :disabled="p.system && tplForm.role === 'admin'"
                        @change="(e) => {
                          if (!(p.system && tplForm.role === 'admin')) {
                            tplForm.pages_enabled[p.key] = (e.target as HTMLInputElement).checked
                          }
                        }"
                      />
                      <label class="form-check-label small" :for="`tpl-chk-${p.key}`">
                        <i v-if="p.system && tplForm.role === 'admin'" class="bi bi-lock-fill me-1" style="font-size:.7rem"></i>
                        {{ p.label }}
                      </label>
                    </div>
                  </div>
                </div>
                <div class="col-12"><hr class="my-1" /></div>
              </template>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showTplModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveTpl">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
