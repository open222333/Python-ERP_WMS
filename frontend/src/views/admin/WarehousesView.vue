<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { Warehouse } from '@/types'

const toast = useToastStore()

// ── State ──────────────────────────────────────────────────
const warehouses = ref<Warehouse[]>([])
const loading    = ref(false)
const saving     = ref(false)
const showModal  = ref(false)

// ── Form ───────────────────────────────────────────────────
interface WarehouseForm {
  _id:         string
  code:        string
  name:        string
  address:     string
  manager:     string
  phone:       string
  description: string
}

function genCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  let r = ''
  for (let i = 0; i < 3; i++) r += chars[Math.floor(Math.random() * chars.length)]
  return `WH-${r}`
}

const emptyForm = (): WarehouseForm => ({
  _id: '', code: genCode(), name: '', address: '', manager: '', phone: '', description: '',
})

const form = ref<WarehouseForm>(emptyForm())

// ── API ────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/warehouse/')
    warehouses.value = data.data ?? data ?? []
  } catch {
    toast.show('載入倉庫失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Modal ──────────────────────────────────────────────────
function openModal(w?: Warehouse) {
  form.value = w
    ? {
        _id:         w._id,
        code:        w.code ?? '',
        name:        w.name,
        address:     w.address ?? '',
        manager:     w.manager ?? '',
        phone:       w.phone ?? '',
        description: w.description ?? '',
      }
    : emptyForm()
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

// ── Save ───────────────────────────────────────────────────
async function save() {
  if (!form.value.name.trim()) {
    toast.show('請填寫倉庫名稱', 'danger')
    return
  }
  saving.value = true
  try {
    const payload = {
      code:        form.value.code.trim(),
      name:        form.value.name.trim(),
      address:     form.value.address.trim(),
      manager:     form.value.manager.trim(),
      phone:       form.value.phone.trim(),
      description: form.value.description.trim(),
    }
    if (form.value._id) {
      await http.put(`/api/warehouse/${form.value._id}`, payload)
    } else {
      await http.post('/warehouse/', payload)
    }
    toast.show('儲存成功', 'success')
    closeModal()
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────
async function del(id: string) {
  if (!confirm('確定要刪除此倉庫？此操作無法復原。')) return
  try {
    await http.delete(`/api/warehouse/${id}`)
    toast.show('已刪除', 'success')
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '刪除失敗', 'danger')
  }
}

onMounted(load)
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-building me-1"></i>倉庫管理</h6>
      <button class="btn btn-sm btn-primary" @click="openModal()">
        <i class="bi bi-plus-lg"></i> 新增倉庫
      </button>
    </div>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>代碼</th>
            <th>名稱</th>
            <th>地址</th>
            <th>負責人</th>
            <th>備註</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!warehouses.length">
            <td colspan="6" class="text-center text-muted py-3">尚無倉庫</td>
          </tr>
          <tr v-for="w in warehouses" :key="w._id">
            <td><code>{{ w.code || '—' }}</code></td>
            <td class="fw-semibold">{{ w.name }}</td>
            <td class="text-muted">{{ w.address || '—' }}</td>
            <td class="text-muted">{{ w.manager || '—' }}</td>
            <td class="text-muted">{{ w.description || '—' }}</td>
            <td>
              <button
                class="btn btn-sm btn-outline-primary me-1"
                @click="openModal(w)"
                title="編輯"
              >
                <i class="bi bi-pencil"></i>
              </button>
              <button
                class="btn btn-sm btn-outline-danger"
                @click="del(w._id)"
                title="刪除"
              >
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Add / Edit Modal -->
  <Teleport to="body">
    <div
      v-if="showModal"
      class="modal d-block"
      style="background: rgba(0,0,0,.5); z-index: 1055;"
      @click.self="closeModal"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-building me-1"></i>
              {{ form._id ? '編輯倉庫' : '新增倉庫' }}
            </h5>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>

          <div class="modal-body">
            <div class="row g-3">
              <!-- Code -->
              <div class="col-md-5">
                <label class="form-label fw-semibold">代碼</label>
                <div class="input-group">
                  <input v-model="form.code" type="text" class="form-control" />
                  <button
                    type="button"
                    class="btn btn-outline-secondary"
                    title="重新產生代碼"
                    @click="form.code = genCode()"
                  >
                    <i class="bi bi-arrow-clockwise"></i>
                  </button>
                </div>
              </div>

              <!-- Name -->
              <div class="col-md-7">
                <label class="form-label fw-semibold">
                  名稱 <span class="text-danger">*</span>
                </label>
                <input
                  v-model="form.name"
                  type="text"
                  class="form-control"
                  placeholder="倉庫名稱"
                />
              </div>

              <!-- Address -->
              <div class="col-12">
                <label class="form-label fw-semibold">地址</label>
                <input v-model="form.address" type="text" class="form-control" placeholder="選填" />
              </div>

              <!-- Manager + Phone -->
              <div class="col-md-6">
                <label class="form-label fw-semibold">負責人</label>
                <input v-model="form.manager" type="text" class="form-control" placeholder="選填" />
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">電話</label>
                <input v-model="form.phone" type="text" class="form-control" placeholder="選填" />
              </div>

              <!-- Description -->
              <div class="col-12">
                <label class="form-label fw-semibold">備註</label>
                <textarea
                  v-model="form.description"
                  class="form-control"
                  rows="2"
                  placeholder="選填"
                ></textarea>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeModal">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="save">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
