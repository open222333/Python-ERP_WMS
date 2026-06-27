<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import http from '@/api'
import { storeApi } from '@/api/store'
import { useToastStore } from '@/stores/toast'
import { fmtDate, ROLE_COLOR, ROLE_LABEL } from '@/utils/format'
import type { User, UserTemplate, Store, StoreRole } from '@/types'

const toast = useToastStore()

// ── State ────────────────────────────────────────────────
const activeTab = ref<'users' | 'templates' | 'stores' | 'store-roles'>('users')
const loading   = ref(false)
const saving    = ref(false)

const users      = ref<User[]>([])
const templates  = ref<UserTemplate[]>([])
const stores     = ref<Store[]>([])
const storeRoles = ref<StoreRole[]>([])

// ── User modal ───────────────────────────────────────────
const showUserModal = ref(false)
const userForm = ref({
  _id:         '',
  username:    '',
  password:    '',
  template_id: '',
  store_ids:   [] as string[],
})
const selectedTemplateMeta = computed(() => {
  if (!userForm.value.template_id) return null
  return templates.value.find(t => t._id === userForm.value.template_id) || null
})

// ── Store modal ──────────────────────────────────────────
const showStoreModal  = ref(false)
const isEditingStore  = ref(false)
const storeForm = ref({ _id: '', name: '', code: '', status: 'active', store_role_id: '' })

// ── StoreRole modal ──────────────────────────────────────
const showStoreRoleModal = ref(false)
const storeRoleForm      = ref({ _id: '', name: '', description: '', is_system: false })

// ── Template modal ───────────────────────────────────────
const showTplModal = ref(false)
const tplForm = ref({
  _id:           '',
  name:          '',
  role:          'operator' as 'admin' | 'operator' | 'viewer',
  description:   '',
  is_system:     false,
  pages_enabled: {} as Record<string, boolean>,
})

// ── Nav pages — 從 nav.ts 取得，與側欄同步 ──────────────────
import { CONFIGURABLE_PAGES } from '@/config/nav'

const pageGroups = computed(() => {
  const map: Record<string, typeof CONFIGURABLE_PAGES> = {}
  for (const p of CONFIGURABLE_PAGES) {
    if (!map[p.group]) map[p.group] = []
    map[p.group].push(p)
  }
  return Object.entries(map)
})

// ── Computed maps ────────────────────────────────────────
const tplMap          = computed(() => Object.fromEntries(templates.value.map(t => [t._id, t])))
const storeMap        = computed(() => Object.fromEntries(stores.value.map(s => [s._id, s])))
const storeRoleMap    = computed(() => Object.fromEntries(storeRoles.value.map(r => [r._id, r.name])))

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
    const [uRes, tRes, sRes, srRes] = await Promise.all([
      http.get('/user/'),
      http.get('/user/templates/'),
      storeApi.getAll(),
      storeApi.roleGetAll(),
    ])
    users.value      = uRes.data?.data  || []
    templates.value  = tRes.data?.data  || []
    stores.value     = sRes.data?.data  || []
    storeRoles.value = srRes.data?.data || []
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
    store_ids:   u?.store_ids ? [...u.store_ids] : [],
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
      const body: Record<string, unknown> = {
        template_id: f.template_id || null,
        store_ids:   f.store_ids,
      }
      if (f.password) body.password = f.password
      await http.put(`/user/${f._id}`, body)
    } else {
      await http.post('/user/', {
        username:    f.username.trim(),
        password:    f.password,
        template_id: f.template_id,
        store_ids:   f.store_ids,
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

// ── Store CRUD ───────────────────────────────────────────
function openCreateStore() {
  const next = stores.value.length + 1
  const suggested = `S${String(next).padStart(3, '0')}`
  storeForm.value = { _id: '', name: '', code: suggested, status: 'active', store_role_id: '' }
  isEditingStore.value = false
  showStoreModal.value = true
}

function openEditStore(s: Store) {
  storeForm.value = {
    _id:           s._id,
    name:          s.name,
    code:          s.code || '',
    status:        s.status || 'active',
    store_role_id: s.store_role_id || '',
  }
  isEditingStore.value = true
  showStoreModal.value = true
}

async function saveStore() {
  if (!storeForm.value.name.trim()) return
  saving.value = true
  try {
    if (isEditingStore.value) {
      await storeApi.update(storeForm.value._id, {
        name:          storeForm.value.name,
        code:          storeForm.value.code,
        status:        storeForm.value.status,
        store_role_id: storeForm.value.store_role_id || null,
      })
      toast.show('店家已更新')
    } else {
      await storeApi.create({
        name:          storeForm.value.name,
        code:          storeForm.value.code,
        store_role_id: storeForm.value.store_role_id || null,
      })
      toast.show('店家已新增')
    }
    showStoreModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteStore(s: Store) {
  if (!confirm(`確定刪除店家「${s.name}」？`)) return
  try {
    await storeApi.delete(s._id)
    toast.show('已刪除')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}

// ── StoreRole CRUD ───────────────────────────────────────
function openStoreRoleModal(r?: StoreRole) {
  storeRoleForm.value = r
    ? { _id: r._id, name: r.name, description: r.description || '', is_system: r.is_system }
    : { _id: '', name: '', description: '', is_system: false }
  showStoreRoleModal.value = true
}

async function saveStoreRole() {
  const f = storeRoleForm.value
  if (!f.name.trim()) { toast.show('角色名稱不得為空', 'danger'); return }
  saving.value = true
  try {
    if (f._id) {
      await storeApi.roleUpdate(f._id, { name: f.name, description: f.description })
    } else {
      await storeApi.roleCreate({ name: f.name.trim(), description: f.description })
    }
    toast.show('儲存成功')
    showStoreRoleModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteStoreRole(r: StoreRole) {
  if (r.is_system) { toast.show('系統預設角色不可刪除', 'danger'); return }
  if (!confirm(`確定刪除店家角色「${r.name}」？`)) return
  try {
    await storeApi.roleDelete(r._id)
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
    const defaultRole = 'operator'
    const pages: Record<string, boolean> = {}
    CONFIGURABLE_PAGES.forEach(p => {
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
    const pages: Record<string, boolean> = {}
    CONFIGURABLE_PAGES.forEach(p => {
      // 使用者管理對 admin role 永遠鎖定開啟
      if (p.key === 'users' && f.role === 'admin') {
        pages[p.key] = true
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
      <a class="nav-link" :class="{ active: activeTab === 'users' }"
         href="#" @click.prevent="activeTab = 'users'">
        <i class="bi bi-people me-1"></i>使用者
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'templates' }"
         href="#" @click.prevent="activeTab = 'templates'">
        <i class="bi bi-person-badge me-1"></i>使用者模板
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'stores' }"
         href="#" @click.prevent="activeTab = 'stores'">
        <i class="bi bi-shop me-1"></i>店家
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'store-roles' }"
         href="#" @click.prevent="activeTab = 'store-roles'">
        <i class="bi bi-tags me-1"></i>店家角色模板
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
          <tr><th>帳號</th><th>角色</th><th>使用者模板</th><th>所屬店家</th><th>建立時間</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!users.length">
            <td colspan="6" class="text-center text-muted py-3">無使用者</td>
          </tr>
          <tr v-for="u in users" :key="u._id">
            <td>
              <i class="bi bi-person-circle me-1 text-muted"></i>
              <strong>{{ u.username }}</strong>
              <span v-if="u.locked" class="badge bg-warning text-dark ms-1" style="font-size:.65rem">
                <i class="bi bi-lock-fill me-1"></i>系統
              </span>
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
            <td>
              <template v-if="u.store_ids && u.store_ids.length">
                <span v-for="sid in u.store_ids" :key="sid"
                      class="badge bg-secondary me-1">
                  <i class="bi bi-shop me-1"></i>{{ storeMap[sid]?.name ?? sid }}
                </span>
              </template>
              <span v-else class="text-muted small">—</span>
            </td>
            <td class="text-muted small">{{ fmtDate(u.created_at) }}</td>
            <td>
              <button class="btn btn-sm btn-outline-primary me-1"
                      :disabled="u.locked"
                      @click="openUserModal(u)">
                <i class="bi bi-pencil"></i>
              </button>
              <button v-if="u.locked" class="btn btn-sm btn-outline-secondary" disabled
                      :title="`系統帳號「${u.username}」不可刪除`">
                <i class="bi bi-lock-fill"></i>
              </button>
              <button v-else class="btn btn-sm btn-outline-danger"
                      @click="deleteUser(u._id, u.username)">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Templates Tab ─────────────────────────────────── -->
  <div v-else-if="activeTab === 'templates'" class="table-card">
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
              <button v-if="!t.is_system" class="btn btn-sm btn-outline-danger"
                      @click="deleteTpl(t._id, t.name)">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Stores Tab ─────────────────────────────────────── -->
  <div v-else-if="activeTab === 'stores'" class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-shop me-1"></i>店家列表</h6>
      <button class="btn btn-sm btn-primary" @click="openCreateStore">
        <i class="bi bi-plus-lg"></i> 新增店家
      </button>
    </div>
    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr><th>店家名稱</th><th>代碼</th><th>角色</th><th>狀態</th><th>建立時間</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!stores.length">
            <td colspan="6" class="text-center text-muted py-3">尚無店家</td>
          </tr>
          <tr v-for="s in stores" :key="s._id">
            <td><i class="bi bi-shop me-1 text-muted"></i><strong>{{ s.name }}</strong></td>
            <td><code>{{ s.code || '—' }}</code></td>
            <td class="text-muted small">
              {{ s.store_role_id ? (storeRoleMap[s.store_role_id] ?? '—') : '—' }}
            </td>
            <td>
              <span class="badge" :class="s.status === 'active' ? 'bg-success' : 'bg-secondary'">
                {{ s.status === 'active' ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="text-muted small">{{ fmtDate(s.created_at) }}</td>
            <td>
              <button class="btn btn-sm btn-outline-primary me-1" @click="openEditStore(s)">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" @click="deleteStore(s)">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── StoreRoles Tab ─────────────────────────────────── -->
  <div v-else-if="activeTab === 'store-roles'" class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-tags me-1"></i>店家角色模板</h6>
      <button class="btn btn-sm btn-primary" @click="openStoreRoleModal()">
        <i class="bi bi-plus-lg"></i> 新增角色
      </button>
    </div>
    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr><th>名稱</th><th>說明</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="3" class="text-center py-3">
              <div class="spinner-border spinner-border-sm"></div>
            </td>
          </tr>
          <tr v-else-if="!storeRoles.length">
            <td colspan="3" class="text-center text-muted py-3">尚無角色模板</td>
          </tr>
          <tr v-for="r in storeRoles" :key="r._id">
            <td>
              <strong>{{ r.name }}</strong>
              <span v-if="r.is_system" class="badge bg-secondary ms-1" style="font-size:.65rem">系統</span>
            </td>
            <td class="text-muted small">
              {{ r.description || '—' }}
              <span v-if="r.is_system" class="text-muted ms-1">（系統預設，不可刪除）</span>
            </td>
            <td>
              <button
                class="btn btn-sm btn-outline-primary me-1"
                :disabled="r.is_system"
                @click="openStoreRoleModal(r)"
              >
                <i class="bi bi-pencil"></i>
              </button>
              <button
                class="btn btn-sm btn-outline-danger"
                :disabled="r.is_system"
                @click="deleteStoreRole(r)"
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
    <div v-if="showUserModal" class="modal d-block" style="background: rgba(0,0,0,.45)"
         @click.self="showUserModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">使用者帳號</h5>
            <button type="button" class="btn-close" @click="showUserModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">帳號 <span v-if="!userForm._id" class="text-danger">*</span></label>
              <input v-model="userForm.username" type="text" class="form-control"
                     :disabled="!!userForm._id" />
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
                <span class="badge"
                      :class="selectedTemplateMeta ? `bg-${ROLE_COLOR[selectedTemplateMeta.role]}` : 'bg-secondary'">
                  {{ selectedTemplateMeta ? ROLE_LABEL[selectedTemplateMeta.role] : '—' }}
                </span>
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label">所屬店家
                <span class="text-muted small ms-1">（可多選，限定該使用者只看到已勾選的店家資料）</span>
              </label>
              <div class="border rounded p-2" style="max-height:180px; overflow-y:auto">
                <div v-if="!stores.length" class="text-muted small py-1 px-1">尚無店家</div>
                <div v-for="s in stores" :key="s._id" class="form-check">
                  <input :id="`usr-store-${s._id}`" class="form-check-input" type="checkbox"
                         :value="s._id"
                         :checked="userForm.store_ids.includes(s._id)"
                         @change="(e) => {
                           const checked = (e.target as HTMLInputElement).checked
                           if (checked) {
                             userForm.store_ids = [...userForm.store_ids, s._id]
                           } else {
                             userForm.store_ids = userForm.store_ids.filter(id => id !== s._id)
                           }
                         }" />
                  <label class="form-check-label small" :for="`usr-store-${s._id}`">
                    {{ s.name }}（{{ s.code }}）
                  </label>
                </div>
              </div>
              <div class="form-text mt-1">不勾選表示不綁定特定店家（可看到所有資料）</div>
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

  <!-- ══════════ Store Modal ══════════ -->
  <Teleport to="body">
    <div v-if="showStoreModal" class="modal d-block" style="background: rgba(0,0,0,.45)"
         @click.self="showStoreModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ isEditingStore ? '編輯店家' : '新增店家' }}</h5>
            <button class="btn-close" @click="showStoreModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">店家名稱 <span class="text-danger">*</span></label>
              <input v-model="storeForm.name" class="form-control" placeholder="例：台北信義店" />
            </div>
            <div class="mb-3">
              <label class="form-label">店家代碼</label>
              <input v-model="storeForm.code" class="form-control" placeholder="例：S001" />
              <div v-if="!isEditingStore" class="form-text">自動產生，可手動修改</div>
            </div>
            <div class="mb-3">
              <label class="form-label">店家角色</label>
              <select v-model="storeForm.store_role_id" class="form-select">
                <option value="">— 不指派 —</option>
                <option v-for="r in storeRoles" :key="r._id" :value="r._id">{{ r.name }}</option>
              </select>
            </div>
            <div v-if="isEditingStore" class="mb-3">
              <label class="form-label">狀態</label>
              <select v-model="storeForm.status" class="form-select">
                <option value="active">啟用</option>
                <option value="inactive">停用</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showStoreModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving || !storeForm.name.trim()" @click="saveStore">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              {{ isEditingStore ? '儲存' : '新增' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ══════════ StoreRole Modal ══════════ -->
  <Teleport to="body">
    <div v-if="showStoreRoleModal" class="modal d-block" style="background: rgba(0,0,0,.45)"
         @click.self="showStoreRoleModal = false">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ storeRoleForm._id ? '編輯店家角色' : '新增店家角色' }}</h5>
            <button class="btn-close" @click="showStoreRoleModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">角色名稱 <span class="text-danger">*</span></label>
              <input v-model="storeRoleForm.name" class="form-control" placeholder="例：加盟店"
                     :disabled="storeRoleForm.is_system" />
            </div>
            <div class="mb-3">
              <label class="form-label">說明</label>
              <input v-model="storeRoleForm.description" class="form-control" placeholder="選填" />
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showStoreRoleModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving || !storeRoleForm.name.trim()" @click="saveStoreRole">
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
    <div v-if="showTplModal" class="modal d-block" style="background: rgba(0,0,0,.45)"
         @click.self="showTplModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ tplForm._id ? '編輯使用者模板' : '新增使用者模板' }}</h5>
            <button type="button" class="btn-close" @click="showTplModal = false"></button>
          </div>
          <div class="modal-body">
            <div v-if="tplForm.is_system" class="alert alert-warning py-2 small mb-3">
              <i class="bi bi-lock-fill me-1"></i>
              系統預設模板：名稱與角色不可修改，但可調整頁面顯示設定。
            </div>
            <div class="mb-3">
              <label class="form-label">模板名稱 <span class="text-danger">*</span></label>
              <input v-model="tplForm.name" type="text" class="form-control"
                     :disabled="tplForm.is_system" placeholder="例：收銀員、倉管人員" />
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
              <input v-model="tplForm.description" type="text" class="form-control"
                     placeholder="選填，簡短描述此模板用途" />
            </div>
            <hr />
            <div class="mb-2 fw-semibold">頁面顯示設定</div>
            <p class="text-muted small mb-3">
              勾選此模板的使用者可在後台側欄看到哪些功能頁面。未勾選的頁面將會隱藏。
            </p>
            <div class="row g-2">
              <template v-for="[group, pages] in pageGroups" :key="group">
                <div class="col-12">
                  <div class="text-muted small fw-semibold mb-1"
                       style="font-size:.72rem; letter-spacing:.05em; text-transform:uppercase">
                    {{ group }}
                  </div>
                  <div class="d-flex flex-wrap gap-2 mb-1">
                    <div v-for="p in pages" :key="p.key" class="form-check form-check-inline"
                         :title="p.key === 'users' && tplForm.role === 'admin' ? '使用者管理對管理員模板固定開啟' : ''">
                      <input :id="`tpl-chk-${p.key}`" class="form-check-input" type="checkbox"
                             :checked="(p.key === 'users' && tplForm.role === 'admin') ? true : tplForm.pages_enabled[p.key] !== false"
                             :disabled="p.key === 'users' && tplForm.role === 'admin'"
                             @change="(e) => {
                               if (!(p.key === 'users' && tplForm.role === 'admin')) {
                                 tplForm.pages_enabled[p.key] = (e.target as HTMLInputElement).checked
                               }
                             }" />
                      <label class="form-check-label small" :for="`tpl-chk-${p.key}`">
                        <i v-if="p.key === 'users' && tplForm.role === 'admin'" class="bi bi-lock-fill me-1"
                           style="font-size:.7rem"></i>
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
