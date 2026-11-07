<!-- [U10] 自 views/admin/ProductsView.vue 拆出 -->
<script setup lang="ts">
import { ref } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import type { Category } from '@/types'
import { appConfirm } from '@/composables/useConfirm'
import { useFieldErrors } from '@/composables/useFieldErrors'

defineProps<{ categories: Category[] }>()
const emit = defineEmits<{ (e: 'reload'): void }>()

const toast = useToastStore()
const fe    = useFieldErrors()   // [U9]

interface CategoryForm { _id: string; name: string; sort_order: number }
const catForm     = ref<CategoryForm>({ _id: '', name: '', sort_order: 0 })
const showCatModal = ref(false)
const catSaving    = ref(false)

function openCatModal(cat?: Category) {
  fe.clear()
  catForm.value = cat
    ? { _id: cat._id, name: cat.name, sort_order: cat.sort_order ?? 0 }
    : { _id: '', name: '', sort_order: 0 }
  showCatModal.value = true
}

async function saveCat() {
  if (!fe.check({ cat_name: [!catForm.value.name.trim(), '請填寫分類名稱'] })) return   // [U9]
  catSaving.value = true
  try {
    const payload = { name: catForm.value.name.trim(), sort_order: Number(catForm.value.sort_order) }
    if (catForm.value._id) {
      await http.put(`/product/category/${catForm.value._id}`, payload)
    } else {
      await http.post('/product/category/', payload)
    }
    toast.show('儲存成功', 'success')
    showCatModal.value = false
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    catSaving.value = false
  }
}

async function delCat(id: string) {
  if (!(await appConfirm('確定要刪除此分類？', { danger: true }))) return
  try {
    await http.delete(`/product/category/${id}`)
    toast.show('已刪除', 'success')
    emit('reload')
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '刪除失敗', 'danger')
  }
}
</script>

<template>
<!-- ── 產品分類 Tab ─────────────────────────────────── -->
<div class="table-card">
  <div class="table-header">
    <h6><i class="bi bi-tags me-1"></i>產品分類</h6>
    <button class="btn btn-sm btn-primary" @click="openCatModal()">
      <i class="bi bi-plus-lg"></i> 新增分類
    </button>
  </div>
  <div class="table-responsive">
    <table v-stack-table class="table mb-0">
      <thead>
        <tr><th>名稱</th><th>排序</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-if="!categories.length">
          <td colspan="3" class="text-center text-muted py-3">尚無分類</td>
        </tr>
        <tr v-for="c in categories" :key="c._id">
          <td class="fw-semibold">{{ c.name }}</td>
          <td class="text-muted">{{ c.sort_order ?? 0 }}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary me-1" @click="openCatModal(c)" aria-label="編輯" title="編輯">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" @click="delCat(c._id)" aria-label="刪除" title="刪除">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Category Modal -->
<Teleport to="body">
  <div v-if="showCatModal" class="modal d-block bg-dim-50 z-1055"
       @click.self="showCatModal = false">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            <i class="bi bi-tags me-1"></i>
            {{ catForm._id ? '編輯分類' : '新增分類' }}
          </h5>
          <button type="button" class="btn-close" @click="showCatModal = false"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label fw-semibold">名稱 <span class="text-danger">*</span></label>
            <input v-model="catForm.name" type="text" class="form-control" placeholder="分類名稱"
                   data-field="cat_name" :class="{ 'is-invalid': fe.errors.cat_name }"
                   @input="fe.clear('cat_name')"
                   @keydown.enter="(e) => !e.isComposing && saveCat()" />
            <div class="invalid-feedback">{{ fe.errors.cat_name }}</div>
          </div>
          <div class="mb-3">
            <label class="form-label fw-semibold">排序</label>
            <input v-model.number="catForm.sort_order" type="number" class="form-control" min="0" placeholder="0" />
            <div class="form-text">數字越小越靠前，預設 0</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCatModal = false">取消</button>
          <button class="btn btn-primary" :disabled="catSaving" @click="saveCat">
            <span v-if="catSaving" class="spinner-border spinner-border-sm me-1"></span>
            儲存
          </button>
        </div>
      </div>
    </div>
  </div>
</Teleport>
</template>
