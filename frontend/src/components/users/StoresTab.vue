<!-- [U10] 自 views/admin/UsersView.vue 拆出（原本四個分頁＋四個彈窗共 836 行同一檔）-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeApi } from '@/api/store'
import { useToastStore } from '@/stores/toast'
import { fmtDate } from '@/utils/format'
import type { Store, StoreRole } from '@/types'
import { useFieldErrors } from '@/composables/useFieldErrors'
import { appConfirm } from '@/composables/useConfirm'

const props = defineProps<{
  stores:     Store[]
  storeRoles: StoreRole[]
  loading:    boolean
}>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const toast  = useToastStore()
const fe     = useFieldErrors()   // [U9]
const saving = ref(false)

const storeRoleMap = computed(() => Object.fromEntries(props.storeRoles.map(r => [r._id, r.name])))

// ── Store modal ──────────────────────────────────────────
const showStoreModal  = ref(false)
const isEditingStore  = ref(false)
const storeForm = ref({ _id: '', name: '', code: '', status: 'active', store_role_id: '' })

// ── Store CRUD ───────────────────────────────────────────
function openCreateStore() {
  fe.clear()
  const next = props.stores.length + 1
  const suggested = `S${String(next).padStart(3, '0')}`
  storeForm.value = { _id: '', name: '', code: suggested, status: 'active', store_role_id: '' }
  isEditingStore.value = false
  showStoreModal.value = true
}

function openEditStore(s: Store) {
  fe.clear()
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
  if (!fe.check({ store_name: [!storeForm.value.name.trim(), '請填寫店家名稱'] })) return   // [U9] 原本按鈕 disabled、無提示
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
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteStore(s: Store) {
  if (!(await appConfirm(`確定刪除店家「${s.name}」？`, { danger: true }))) return
  try {
    await storeApi.delete(s._id)
    toast.show('已刪除')
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}
</script>

<template>
<!-- ── Stores Tab ─────────────────────────────────────── -->
<div class="table-card">
  <div class="table-header">
    <h6><i class="bi bi-shop me-1"></i>店家列表</h6>
    <button class="btn btn-sm btn-primary" @click="openCreateStore">
      <i class="bi bi-plus-lg"></i> 新增店家
    </button>
  </div>
  <div class="table-responsive">
    <table v-stack-table class="table mb-0">
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
            <button class="btn btn-sm btn-outline-primary me-1" @click="openEditStore(s)" aria-label="編輯" title="編輯">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" @click="deleteStore(s)" aria-label="刪除" title="刪除">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ══════════ Store Modal ══════════ -->
<Teleport to="body">
  <div v-if="showStoreModal" class="modal d-block bg-dim-45"
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
            <input v-model="storeForm.name" class="form-control" placeholder="例：台北信義店"
                   data-field="store_name" :class="{ 'is-invalid': fe.errors.store_name }"
                   @input="fe.clear('store_name')" />
            <div class="invalid-feedback">{{ fe.errors.store_name }}</div>
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
          <button class="btn btn-primary" :disabled="saving" @click="saveStore">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            {{ isEditingStore ? '儲存' : '新增' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</Teleport>
</template>
