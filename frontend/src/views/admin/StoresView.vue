<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeApi } from '@/api/store'
import { useToastStore } from '@/stores/toast'
import { fmtDate, ROLE_COLOR, ROLE_LABEL } from '@/utils/format'
import type { Store, User } from '@/types'
import { appConfirm } from '@/composables/useConfirm'
import { useFieldErrors } from '@/composables/useFieldErrors'

const toast = useToastStore()
// [U9] 欄位層級錯誤（分店表單、帳號表單各一組）。原本按鈕直接 disabled，使用者不知道缺什麼
const feStore = useFieldErrors()
const feUser  = useFieldErrors()

const activeTab = ref<'stores' | 'accounts'>('stores')
const loading   = ref(false)
const saving    = ref(false)

// ── 分店列表 ──────────────────────────────────────────────
const stores = ref<Store[]>([])

const showStoreModal = ref(false)
const storeForm = ref({ _id: '', name: '', code: '', status: 'active' })
const isEditingStore = ref(false)

async function loadStores() {
  loading.value = true
  try {
    const r = await storeApi.getAll()
    stores.value = r.data.data || []
  } finally {
    loading.value = false
  }
}

function openCreateStore() {
  feStore.clear()
  storeForm.value = { _id: '', name: '', code: '', status: 'active' }
  isEditingStore.value = false
  showStoreModal.value = true
}

function openEditStore(s: Store) {
  feStore.clear()
  storeForm.value = { _id: s._id, name: s.name, code: s.code || '', status: s.status || 'active' }
  isEditingStore.value = true
  showStoreModal.value = true
}

async function saveStore() {
  if (!feStore.check({ store_name: [!storeForm.value.name.trim(), '請填寫分店名稱'] })) return
  saving.value = true
  try {
    if (isEditingStore.value) {
      await storeApi.update(storeForm.value._id, {
        name:   storeForm.value.name,
        code:   storeForm.value.code,
        status: storeForm.value.status,
      })
      toast.success('分店已更新')
    } else {
      await storeApi.create({ name: storeForm.value.name, code: storeForm.value.code })
      toast.success('分店已新增')
    }
    showStoreModal.value = false
    await loadStores()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || '儲存失敗')
  } finally {
    saving.value = false
  }
}

async function deleteStore(s: Store) {
  if (!(await appConfirm(`確定刪除分店「${s.name}」？此操作無法復原。`, { danger: true }))) return
  try {
    await storeApi.delete(s._id)
    toast.success('已刪除')
    await loadStores()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || '刪除失敗')
  }
}

// ── 分店帳號 ──────────────────────────────────────────────
const selectedStoreId   = ref('')
const selectedStoreName = ref('')
const storeUsers        = ref<User[]>([])

const showUserModal = ref(false)
const userForm = ref({ username: '', password: '', role: 'viewer' as string })

async function selectStore(s: Store) {
  selectedStoreId.value   = s._id
  selectedStoreName.value = s.name
  activeTab.value         = 'accounts'
  await loadStoreUsers()
}

async function loadStoreUsers() {
  if (!selectedStoreId.value) return
  loading.value = true
  try {
    const r = await storeApi.getUsers(selectedStoreId.value)
    storeUsers.value = r.data.data || []
  } finally {
    loading.value = false
  }
}

function openCreateUser() {
  feUser.clear()
  userForm.value = { username: '', password: '', role: 'viewer' }
  showUserModal.value = true
}

async function saveUser() {
  const pw = userForm.value.password
  if (!feUser.check({
    su_username: [!userForm.value.username.trim(), '請填寫使用者名稱'],
    su_password: [!pw.trim() || pw.length < 6, pw.trim() ? '密碼至少 6 碼' : '請設定密碼'],
  })) return
  saving.value = true
  try {
    await storeApi.createUser(selectedStoreId.value, userForm.value)
    toast.success('帳號已建立')
    showUserModal.value = false
    await loadStoreUsers()
  } catch (e: any) {
    toast.error(e?.response?.data?.message || '建立失敗')
  } finally {
    saving.value = false
  }
}

onMounted(loadStores)
</script>

<template>
  <div class="container-fluid py-3">
    <div class="d-flex align-items-center mb-3 gap-2">
      <h5 class="mb-0"><i class="bi bi-shop me-2"></i>分店管理</h5>
    </div>

    <!-- Tabs -->
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: activeTab === 'stores' }" @click="activeTab = 'stores'">
          <i class="bi bi-shop me-1"></i>分店列表
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: activeTab === 'accounts' }" @click="activeTab = 'accounts'">
          <i class="bi bi-people me-1"></i>分店帳號
          <span v-if="selectedStoreName" class="badge bg-secondary ms-1">{{ selectedStoreName }}</span>
        </button>
      </li>
    </ul>

    <!-- ── Tab 1: 分店列表 ── -->
    <div v-if="activeTab === 'stores'">
      <div class="d-flex justify-content-between mb-3">
        <span class="text-muted small">共 {{ stores.length }} 間分店</span>
        <button class="btn btn-primary btn-sm" @click="openCreateStore">
          <i class="bi bi-plus-lg me-1"></i>新增分店
        </button>
      </div>

      <div v-if="loading" class="text-center py-5 text-muted">
        <div class="spinner-border spinner-border-sm me-2"></div>載入中…
      </div>

      <div v-else-if="stores.length === 0" class="text-center py-5 text-muted">
        <i class="bi bi-shop fs-2 d-block mb-2"></i>尚無分店，點擊「新增分店」開始建立
      </div>

      <div v-else class="table-responsive">
        <table v-stack-table class="table table-hover align-middle">
          <thead class="table-light">
            <tr>
              <th>分店名稱</th>
              <th>代碼</th>
              <th>狀態</th>
              <th>建立時間</th>
              <th class="text-end">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stores" :key="s._id">
              <td>
                <i class="bi bi-shop me-1 text-muted"></i>
                <strong>{{ s.name }}</strong>
              </td>
              <td><code>{{ s.code || '—' }}</code></td>
              <td>
                <span class="badge" :class="s.status === 'active' ? 'bg-success' : 'bg-secondary'">
                  {{ s.status === 'active' ? '啟用' : '停用' }}
                </span>
              </td>
              <td class="text-muted small">{{ fmtDate(s.created_at) }}</td>
              <td class="text-end">
                <button class="btn btn-outline-secondary btn-sm me-1" title="查看帳號" @click="selectStore(s)">
                  <i class="bi bi-people"></i>
                </button>
                <button class="btn btn-outline-primary btn-sm me-1" @click="openEditStore(s)" aria-label="編輯" title="編輯">
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-outline-danger btn-sm" @click="deleteStore(s)" aria-label="刪除" title="刪除">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Tab 2: 分店帳號 ── -->
    <div v-if="activeTab === 'accounts'">
      <div v-if="!selectedStoreId" class="text-center py-5 text-muted">
        <i class="bi bi-arrow-left-circle fs-2 d-block mb-2"></i>
        請在「分店列表」點擊
        <i class="bi bi-people"></i>
        按鈕選擇分店
      </div>

      <template v-else>
        <div class="d-flex justify-content-between align-items-center mb-3">
          <div>
            <span class="text-muted small">分店：</span>
            <strong>{{ selectedStoreName }}</strong>
            <span class="text-muted small ms-2">共 {{ storeUsers.length }} 個帳號</span>
          </div>
          <button class="btn btn-primary btn-sm" @click="openCreateUser">
            <i class="bi bi-plus-lg me-1"></i>新增帳號
          </button>
        </div>

        <div v-if="loading" class="text-center py-5 text-muted">
          <div class="spinner-border spinner-border-sm me-2"></div>載入中…
        </div>

        <div v-else-if="storeUsers.length === 0" class="text-center py-5 text-muted">
          <i class="bi bi-person-x fs-2 d-block mb-2"></i>此分店尚無帳號
        </div>

        <div v-else class="table-responsive">
          <table v-stack-table class="table table-hover align-middle">
            <thead class="table-light">
              <tr>
                <th>使用者名稱</th>
                <th>角色</th>
                <th>建立時間</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in storeUsers" :key="u._id">
                <td><i class="bi bi-person me-1 text-muted"></i>{{ u.username }}</td>
                <td>
                  <span class="badge" :class="`bg-${ROLE_COLOR[u.role] ?? 'secondary'}`">
                    {{ ROLE_LABEL[u.role] ?? u.role }}
                  </span>
                </td>
                <td class="text-muted small">{{ fmtDate(u.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>

  <!-- ── 分店 Modal ── -->
  <Teleport to="body">
    <div v-if="showStoreModal" class="modal d-block bg-dim-40" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ isEditingStore ? '編輯分店' : '新增分店' }}</h5>
            <button class="btn-close" @click="showStoreModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">分店名稱 <span class="text-danger">*</span></label>
              <input v-model="storeForm.name" class="form-control" placeholder="例：台北信義店"
                     data-field="store_name" :class="{ 'is-invalid': feStore.errors.store_name }"
                     @input="feStore.clear('store_name')" />
              <div class="invalid-feedback">{{ feStore.errors.store_name }}</div>
            </div>
            <div v-if="isEditingStore" class="mb-3">
              <label class="form-label">分店代碼</label>
              <input v-model="storeForm.code" class="form-control" />
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
            <button class="btn btn-primary" :disabled="saving" @click="saveStore">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              {{ isEditingStore ? '儲存' : '新增' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── 新增帳號 Modal ── -->
  <Teleport to="body">
    <div v-if="showUserModal" class="modal d-block bg-dim-40" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">新增分店帳號</h5>
            <button class="btn-close" @click="showUserModal = false"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted small mb-3">分店：<strong>{{ selectedStoreName }}</strong></p>
            <div class="mb-3">
              <label class="form-label">使用者名稱 <span class="text-danger">*</span></label>
              <input v-model="userForm.username" class="form-control" placeholder="登入帳號" autocomplete="off"
                     data-field="su_username" :class="{ 'is-invalid': feUser.errors.su_username }"
                     @input="feUser.clear('su_username')" />
              <div class="invalid-feedback">{{ feUser.errors.su_username }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label">密碼 <span class="text-danger">*</span></label>
              <input v-model="userForm.password" type="password" class="form-control" placeholder="至少 6 碼" autocomplete="new-password"
                     data-field="su_password" :class="{ 'is-invalid': feUser.errors.su_password }"
                     @input="feUser.clear('su_password')" />
              <div class="invalid-feedback">{{ feUser.errors.su_password }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label">角色</label>
              <select v-model="userForm.role" class="form-select">
                <option value="admin">Admin（管理員）</option>
                <option value="operator">Operator（操作員）</option>
                <option value="cashier">Cashier（收銀員）</option>
                <option value="viewer">Viewer（唯讀）</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showUserModal = false">取消</button>
            <button class="btn btn-primary"
              :disabled="saving"
              @click="saveUser">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              建立帳號
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
