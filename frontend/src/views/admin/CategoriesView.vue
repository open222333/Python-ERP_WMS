<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { Category } from '@/types'

const toast = useToastStore()

// ── State ──────────────────────────────────────────────────
const categories = ref<Category[]>([])
const loading    = ref(false)
const saving     = ref(false)
const showModal  = ref(false)

interface CategoryForm {
  _id:        string
  name:       string
  sort_order: number
}

const emptyForm = (): CategoryForm => ({ _id: '', name: '', sort_order: 0 })
const form = ref<CategoryForm>(emptyForm())

// ── API ────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/product/category/')
    categories.value = data.data ?? data ?? []
  } catch {
    toast.show('載入分類失敗', 'danger')
  } finally {
    loading.value = false
  }
}

// ── Modal ──────────────────────────────────────────────────
function openModal(cat?: Category) {
  form.value = cat
    ? { _id: cat._id, name: cat.name, sort_order: cat.sort_order ?? 0 }
    : emptyForm()
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

// ── Save ───────────────────────────────────────────────────
async function save() {
  if (!form.value.name.trim()) {
    toast.show('請填寫分類名稱', 'danger')
    return
  }
  saving.value = true
  try {
    const payload = { name: form.value.name.trim(), sort_order: Number(form.value.sort_order) }
    if (form.value._id) {
      await http.put(`/product/category/${form.value._id}`, payload)
    } else {
      await http.post('/product/category/', payload)
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
  if (!confirm('確定要刪除此分類？')) return
  try {
    await http.delete(`/product/category/${id}`)
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
      <h6><i class="bi bi-tags me-1"></i>產品分類</h6>
      <button class="btn btn-sm btn-primary" @click="openModal()">
        <i class="bi bi-plus-lg"></i> 新增分類
      </button>
    </div>

    <div class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>名稱</th>
            <th>排序</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="3" class="text-center py-3">
              <div class="spinner-border spinner-border-sm text-primary"></div>
            </td>
          </tr>
          <tr v-else-if="!categories.length">
            <td colspan="3" class="text-center text-muted py-3">尚無分類</td>
          </tr>
          <tr v-for="c in categories" :key="c._id">
            <td class="fw-semibold">{{ c.name }}</td>
            <td class="text-muted">{{ c.sort_order ?? 0 }}</td>
            <td>
              <button
                class="btn btn-sm btn-outline-primary me-1"
                @click="openModal(c)"
                title="編輯"
              >
                <i class="bi bi-pencil"></i>
              </button>
              <button
                class="btn btn-sm btn-outline-danger"
                @click="del(c._id)"
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
              <i class="bi bi-tags me-1"></i>
              {{ form._id ? '編輯分類' : '新增分類' }}
            </h5>
            <button type="button" class="btn-close" @click="closeModal"></button>
          </div>

          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold">
                名稱 <span class="text-danger">*</span>
              </label>
              <input
                v-model="form.name"
                type="text"
                class="form-control"
                placeholder="分類名稱"
                @keydown.enter="save"
              />
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">排序</label>
              <input
                v-model.number="form.sort_order"
                type="number"
                class="form-control"
                min="0"
                placeholder="0"
              />
              <div class="form-text">數字越小越靠前，預設 0</div>
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
