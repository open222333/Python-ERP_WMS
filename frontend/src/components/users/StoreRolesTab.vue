<!-- [U10] 自 views/admin/UsersView.vue 拆出（原本四個分頁＋四個彈窗共 836 行同一檔）-->
<script setup lang="ts">
import { ref } from 'vue'
import { storeApi } from '@/api/store'
import { useToastStore } from '@/stores/toast'
import type { StoreRole } from '@/types'
import { useFieldErrors } from '@/composables/useFieldErrors'
import { appConfirm } from '@/composables/useConfirm'

defineProps<{
  storeRoles: StoreRole[]
  loading:    boolean
}>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const toast  = useToastStore()
const fe     = useFieldErrors()   // [U9]
const saving = ref(false)

// ── StoreRole modal ──────────────────────────────────────
const showStoreRoleModal = ref(false)
const storeRoleForm      = ref({ _id: '', name: '', description: '', is_system: false })

// ── StoreRole CRUD ───────────────────────────────────────
function openStoreRoleModal(r?: StoreRole) {
  fe.clear()
  storeRoleForm.value = r
    ? { _id: r._id, name: r.name, description: r.description || '', is_system: r.is_system }
    : { _id: '', name: '', description: '', is_system: false }
  showStoreRoleModal.value = true
}

async function saveStoreRole() {
  const f = storeRoleForm.value
  if (!fe.check({ role_name: [!f.name.trim(), '角色名稱不得為空'] })) return
  saving.value = true
  try {
    if (f._id) {
      await storeApi.roleUpdate(f._id, { name: f.name, description: f.description })
    } else {
      await storeApi.roleCreate({ name: f.name.trim(), description: f.description })
    }
    toast.show('儲存成功')
    showStoreRoleModal.value = false
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteStoreRole(r: StoreRole) {
  if (r.is_system) { toast.show('系統預設角色不可刪除', 'danger'); return }
  if (!(await appConfirm(`確定刪除店家角色「${r.name}」？`, { danger: true }))) return
  try {
    await storeApi.roleDelete(r._id)
    toast.show('已刪除')
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}
</script>

<template>
<!-- ── StoreRoles Tab ─────────────────────────────────── -->
<div class="table-card">
  <div class="table-header">
    <h6><i class="bi bi-tags me-1"></i>店家角色模板</h6>
    <button class="btn btn-sm btn-primary" @click="openStoreRoleModal()">
      <i class="bi bi-plus-lg"></i> 新增角色
    </button>
  </div>
  <div class="table-responsive">
    <table v-stack-table class="table mb-0">
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
            <span v-if="r.is_system" class="badge bg-secondary ms-1 fz-65">系統</span>
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
             aria-label="編輯" title="編輯">
              <i class="bi bi-pencil"></i>
            </button>
            <button
              class="btn btn-sm btn-outline-danger"
              :disabled="r.is_system"
              @click="deleteStoreRole(r)"
             aria-label="刪除" title="刪除">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ══════════ StoreRole Modal ══════════ -->
<Teleport to="body">
  <div v-if="showStoreRoleModal" class="modal d-block bg-dim-45"
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
                   :disabled="storeRoleForm.is_system"
                   data-field="role_name" :class="{ 'is-invalid': fe.errors.role_name }"
                   @input="fe.clear('role_name')" />
            <div class="invalid-feedback">{{ fe.errors.role_name }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label">說明</label>
            <input v-model="storeRoleForm.description" class="form-control" placeholder="選填" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showStoreRoleModal = false">取消</button>
          <button class="btn btn-primary" :disabled="saving" @click="saveStoreRole">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            儲存
          </button>
        </div>
      </div>
    </div>
  </div>
</Teleport>
</template>
