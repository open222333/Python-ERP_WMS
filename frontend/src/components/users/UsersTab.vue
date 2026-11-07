<!-- [U10] 自 views/admin/UsersView.vue 拆出（原本四個分頁＋四個彈窗共 836 行同一檔）-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { fmtDate, ROLE_COLOR, ROLE_LABEL } from '@/utils/format'
import type { User, UserTemplate, Store } from '@/types'
import { useFieldErrors } from '@/composables/useFieldErrors'
import { appConfirm } from '@/composables/useConfirm'

const props = defineProps<{
  users:     User[]
  templates: UserTemplate[]
  stores:    Store[]
  loading:   boolean
}>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const toast  = useToastStore()
const fe     = useFieldErrors()   // [U9]
const saving = ref(false)

const tplMap   = computed(() => Object.fromEntries(props.templates.map(t => [t._id, t])))
const storeMap = computed(() => Object.fromEntries(props.stores.map(s => [s._id, s])))

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
  return props.templates.find(t => t._id === userForm.value.template_id) || null
})

function openUserModal(u?: User) {
  fe.clear()
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
  if (!fe.check({
    username:    [!f._id && !f.username.trim(), '帳號不得為空'],
    password:    [!f._id && !f.password,        '新帳號需設定密碼'],
    template_id: [!f._id && !f.template_id,     '請選擇使用者模板'],
  })) return
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
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteUser(id: string, uname: string) {
  if (!(await appConfirm(`確定刪除使用者 ${uname}？`, { danger: true }))) return
  try {
    await http.delete(`/user/${id}`)
    toast.show('已刪除')
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}
</script>

<template>
<!-- ── Users Tab ─────────────────────────────────────── -->
<div class="table-card">
  <div class="table-header">
    <h6><i class="bi bi-people me-1"></i>使用者列表</h6>
    <button class="btn btn-sm btn-primary" @click="openUserModal()">
      <i class="bi bi-person-plus"></i> 新增使用者
    </button>
  </div>
  <div class="table-responsive">
    <table v-stack-table class="table mb-0">
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
            <span v-if="u.locked" class="badge bg-warning text-dark ms-1 fz-65">
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
                    @click="openUserModal(u)" aria-label="編輯" title="編輯">
              <i class="bi bi-pencil"></i>
            </button>
            <button v-if="u.locked" class="btn btn-sm btn-outline-secondary" disabled
                    :title="`系統帳號「${u.username}」不可刪除`">
              <i class="bi bi-lock-fill"></i>
            </button>
            <button v-else class="btn btn-sm btn-outline-danger"
                    @click="deleteUser(u._id, u.username)" aria-label="刪除" title="刪除">
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
  <div v-if="showUserModal" class="modal d-block bg-dim-45"
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
                   :disabled="!!userForm._id"
                   data-field="username" :class="{ 'is-invalid': fe.errors.username }"
                   @input="fe.clear('username')" />
            <div class="invalid-feedback">{{ fe.errors.username }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label">
              密碼
              <span v-if="!userForm._id" class="text-danger">*</span>
              <span v-else class="text-muted small ms-1">（留空表示不更改）</span>
            </label>
            <input v-model="userForm.password" type="password" class="form-control"
                   :placeholder="userForm._id ? '留空表示不更改' : '設定登入密碼'"
                   autocomplete="new-password"
                   data-field="password" :class="{ 'is-invalid': fe.errors.password }"
                   @input="fe.clear('password')" />
            <div class="invalid-feedback">{{ fe.errors.password }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label">
              使用者模板
              <span v-if="!userForm._id" class="text-danger">*</span>
              <span class="text-muted small ms-1">（決定角色權限與頁面顯示）</span>
            </label>
            <select v-model="userForm.template_id" class="form-select"
                    data-field="template_id" :class="{ 'is-invalid': fe.errors.template_id }"
                    @change="fe.clear('template_id')">
              <option value="">— 不指派 —</option>
              <option v-for="t in templates" :key="t._id" :value="t._id">
                {{ t.name }}（{{ t.role }}）{{ t.is_system ? ' 🔒' : '' }}
              </option>
            </select>
            <div class="invalid-feedback">{{ fe.errors.template_id }}</div>
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
            <div class="border rounded p-2 mhpx-180 overflow-y-auto">
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
</template>
