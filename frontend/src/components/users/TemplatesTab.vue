<!-- [U10] 自 views/admin/UsersView.vue 拆出（原本四個分頁＋四個彈窗共 836 行同一檔）-->
<script setup lang="ts">
import { ref, computed } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { ROLE_COLOR } from '@/utils/format'
import type { User, UserTemplate } from '@/types'
import { CONFIGURABLE_PAGES } from '@/config/nav'
import { useFieldErrors } from '@/composables/useFieldErrors'
import { appConfirm } from '@/composables/useConfirm'

const props = defineProps<{
  templates: UserTemplate[]
  users:     User[]   // 計算各模板已指派人數
}>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const toast  = useToastStore()
const fe     = useFieldErrors()   // [U9]
const saving = ref(false)

const tplUsageMap = computed(() => {
  const m: Record<string, number> = {}
  for (const u of props.users) {
    if (u.template_id) m[u.template_id] = (m[u.template_id] || 0) + 1
  }
  return m
})

// ── Nav pages — 從 nav.ts 取得，與側欄同步 ──────────────────
const pageGroups = computed(() => {
  const map: Record<string, typeof CONFIGURABLE_PAGES> = {}
  for (const p of CONFIGURABLE_PAGES) {
    if (!map[p.group]) map[p.group] = []
    map[p.group].push(p)
  }
  return Object.entries(map)
})

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

// ── Template CRUD ────────────────────────────────────────
function openTplModal(t?: UserTemplate) {
  fe.clear()
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
  if (!fe.check({ tpl_name: [!f.name.trim(), '模板名稱不得為空'] })) return
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
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

async function deleteTpl(id: string, name: string) {
  if (!(await appConfirm(`確定刪除使用者模板「${name}」？\n已指派此模板的使用者角色與頁面設定將不再受此模板控制。`, { danger: true }))) return
  try {
    await http.delete(`/user/templates/${id}`)
    toast.show('模板已刪除')
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '刪除失敗', 'danger')
  }
}
</script>

<template>
<!-- ── Templates Tab ─────────────────────────────────── -->
<div class="table-card">
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
    <table v-stack-table class="table mb-0">
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
            <button class="btn btn-sm btn-outline-primary me-1" @click="openTplModal(t)" aria-label="編輯" title="編輯">
              <i class="bi bi-pencil"></i>
            </button>
            <button v-if="!t.is_system" class="btn btn-sm btn-outline-danger"
                    @click="deleteTpl(t._id, t.name)" aria-label="刪除" title="刪除">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ══════════ Template Modal ══════════ -->
<Teleport to="body">
  <div v-if="showTplModal" class="modal d-block bg-dim-45"
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
                   :disabled="tplForm.is_system" placeholder="例：收銀員、倉管人員"
                   data-field="tpl_name" :class="{ 'is-invalid': fe.errors.tpl_name }"
                   @input="fe.clear('tpl_name')" />
            <div class="invalid-feedback">{{ fe.errors.tpl_name }}</div>
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
                <div class="text-muted small fw-semibold mb-1 fz-72 ls-wide text-uppercase">
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
                      <i v-if="p.key === 'users' && tplForm.role === 'admin'" class="bi bi-lock-fill me-1 fz-70"
                         ></i>
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
