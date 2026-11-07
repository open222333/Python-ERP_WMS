<!-- [U10] 自 views/admin/MenusView.vue 拆出 -->
<script setup lang="ts">
// 品項新增／編輯彈窗。元件常駐（只切換 show），關閉不儲存時表單內容保留為草稿，儲存成功才清空
import { ref } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { useFieldErrors } from '@/composables/useFieldErrors'
import type { LinkedProduct, MenuData, MenuItemData, SimpleProduct, SimpleWarehouse } from './types'

const props = defineProps<{
  menuId:     string
  menu:       MenuData | null   // 父層開啟前已重新載入，選項組為最新
  products:   SimpleProduct[]
  warehouses: SimpleWarehouse[]
}>()
const emit = defineEmits<{ (e: 'saved'): void }>()

const toast  = useToastStore()
const fe     = useFieldErrors()   // [U9]
const saving = ref(false)

// 品項表單
const showItemModal = ref(false)
const itemForm = ref<{
  _id: string; name: string; category: string; price: number; description: string;
  sort_order: number; status: number; consume_inventory: boolean;
  linked_products: LinkedProduct[];
  applied_group_ids: string[];
}>({
  _id: '', name: '', category: '', price: 0, description: '',
  sort_order: 0, status: 1, consume_inventory: false,
  linked_products: [],
  applied_group_ids: [],
})

function addLinkedProduct() {
  itemForm.value.linked_products.push({ product_id: '', warehouse_id: '', consume_qty: 1 })
}
function removeLinkedProduct(idx: number) {
  itemForm.value.linked_products.splice(idx, 1)
}

function open(item?: MenuItemData) {
  fe.clear()
  if (item) {
    // 重新從已更新的 selectedMenuData 取得最新品項資料（若有的話）
    const fresh = props.menu?.items?.find(i => i._id === item._id)
    const src = fresh ?? item
    itemForm.value = {
      _id: src._id, name: src.name, category: src.category || '',
      price: src.price || 0, description: src.description || '',
      sort_order: src.sort_order || 0, status: src.status ?? 1,
      consume_inventory: !!src.consume_inventory,
      linked_products: (src.linked_products || []).map(lp => ({
        product_id:   lp.product_id   || '',
        warehouse_id: lp.warehouse_id || '',
        consume_qty:  lp.consume_qty  || 1,
      })),
      applied_group_ids: [...(src.applied_group_ids || [])],
    }
  } else if (itemForm.value._id) {
    itemForm.value = {
      _id: '', name: '', category: '', price: 0, description: '',
      sort_order: 0, status: 1, consume_inventory: false,
      linked_products: [],
      applied_group_ids: [],
    }
  }
  showItemModal.value = true
}

async function saveItem() {
  const price = itemForm.value.price as unknown
  if (!fe.check({
    item_name:  [!itemForm.value.name.trim(), '請填寫品項名稱'],
    item_price: [price === '' || price === null || Number(price) < 0, '請填寫售價（不可為負數）'],
  })) return
  if (!props.menuId) { toast.show('請先選擇菜單', 'danger'); return }
  saving.value = true
  const isNew = !itemForm.value._id
  try {
    const payload = { ...itemForm.value }
    if (itemForm.value._id) {
      await http.put(`/menu/${props.menuId}/item/${itemForm.value._id}`, payload)
    } else {
      await http.post(`/menu/${props.menuId}/item`, payload)
    }
    toast.show('儲存成功', 'success')
    showItemModal.value = false
    if (isNew) itemForm.value = {
      _id: '', name: '', category: '', price: 0, description: '',
      sort_order: 0, status: 1, consume_inventory: false,
      linked_products: [], applied_group_ids: [],
    }
    emit('saved')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <Teleport to="body">
    <!-- 品項 Modal -->
    <div v-if="showItemModal" class="modal fade show d-block bg-dim-50" @click.self="showItemModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ itemForm._id ? '編輯品項' : '新增品項' }}</h5>
            <button type="button" class="btn-close" @click="showItemModal = false"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-md-8">
                <label class="form-label fw-semibold">品項名稱 <span class="text-danger">*</span></label>
                <input v-model="itemForm.name" type="text" class="form-control" placeholder="例：招牌炒飯"
                     data-field="item_name" :class="{ 'is-invalid': fe.errors.item_name }"
                     @input="fe.clear('item_name')" />
              <div class="invalid-feedback">{{ fe.errors.item_name }}</div>
              </div>
              <div class="col-md-4">
                <label class="form-label fw-semibold">售價 <span class="text-danger">*</span></label>
                <div class="input-group has-validation">
                  <span class="input-group-text">$</span>
                  <input v-model.number="itemForm.price" type="number" class="form-control" min="0" step="1"
                         inputmode="decimal"
                         data-field="item_price" :class="{ 'is-invalid': fe.errors.item_price }"
                         @input="fe.clear('item_price')" />
                  <div class="invalid-feedback">{{ fe.errors.item_price }}</div>
                </div>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">分類</label>
                <input v-model="itemForm.category" type="text" class="form-control"
                       :list="`cat-list-${selectedMenuId}`" placeholder="選擇或輸入分類" />
                <datalist :id="`cat-list-${selectedMenuId}`">
                  <option v-for="c in menu?.categories" :key="c._id" :value="c.name" />
                </datalist>
              </div>
              <div class="col-md-3">
                <label class="form-label fw-semibold">排序</label>
                <input v-model.number="itemForm.sort_order" type="number" class="form-control" min="0" />
              </div>
              <div class="col-md-3">
                <label class="form-label fw-semibold">狀態</label>
                <select v-model.number="itemForm.status" class="form-select">
                  <option :value="1">啟用</option>
                  <option :value="0">停用</option>
                </select>
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold">描述</label>
                <input v-model="itemForm.description" type="text" class="form-control" placeholder="選填" />
              </div>
              <div class="col-12">
                <div class="form-check form-switch">
                  <input v-model="itemForm.consume_inventory" class="form-check-input" type="checkbox" id="item-consume" />
                  <label class="form-check-label fw-semibold" for="item-consume">結帳時消耗庫存</label>
                </div>
                <div class="form-text">開啟後，POS 結帳會扣減對應商品庫存。</div>
              </div>

              <!-- 庫存聯動 -->
              <div class="col-12" v-if="itemForm.consume_inventory">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <label class="form-label fw-semibold mb-0">
                    <i class="bi bi-link-45deg me-1 text-primary"></i>庫存聯動商品
                  </label>
                  <button type="button" class="btn btn-sm btn-outline-primary" @click="addLinkedProduct">
                    <i class="bi bi-plus"></i> 新增
                  </button>
                </div>
                <div v-if="!itemForm.linked_products.length" class="text-muted small fst-italic mb-1">
                  尚未設定聯動商品，結帳時不會扣庫存。
                </div>
                <div v-for="(lp, idx) in itemForm.linked_products" :key="idx"
                     class="linked-row d-flex align-items-center gap-2 mb-2">
                  <select v-model="lp.product_id" class="form-select form-select-sm">
                    <option value="">-- 選擇商品 --</option>
                    <option v-for="p in products" :key="p._id" :value="p._id">
                      {{ p.name }}{{ p.sku ? ` (${p.sku})` : '' }}
                    </option>
                  </select>
                  <select v-model="lp.warehouse_id" class="form-select form-select-sm">
                    <option value="">預設倉庫</option>
                    <option v-for="w in warehouses" :key="w._id" :value="w._id">{{ w.name }}</option>
                  </select>
                  <input v-model.number="lp.consume_qty" type="number" min="1"
                         class="form-control form-control-sm lp-qty" placeholder="扣量" />
                  <button type="button" class="btn btn-sm btn-outline-danger flex-shrink-0"
                          @click="removeLinkedProduct(idx)" aria-label="移除" title="移除">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
                <div class="form-text">每賣出 1 份，依上方設定各扣減指定商品庫存數量。</div>
              </div>
              <!-- 套用客製化選項組 -->
              <div class="col-12" v-if="menu?.option_groups?.length">
                <label class="form-label fw-semibold"><i class="bi bi-sliders2 me-1"></i>客製化選項組</label>
                <div class="d-flex flex-wrap gap-3">
                  <div v-for="og in menu?.option_groups" :key="og._id" class="form-check">
                    <input type="checkbox" :id="`og-cb-${og._id}`" class="form-check-input"
                           :value="og._id" v-model="itemForm.applied_group_ids" />
                    <label :for="`og-cb-${og._id}`" class="form-check-label">
                      {{ og.name }}
                      <span class="text-muted small">（{{ og.choices?.length || 0 }} 選項）</span>
                    </label>
                  </div>
                </div>
                <div class="form-text">勾選後，POS 點此品項時會彈出選項讓顧客選擇。</div>
              </div>
              <div class="col-12" v-else-if="selectedMenuId">
                <div class="text-muted small fst-italic">
                  <i class="bi bi-info-circle me-1"></i>此菜單尚無客製化選項組，可至「客製化」tab 新增。
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showItemModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="saveItem">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>儲存
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 庫存聯動列 */
.linked-row .form-select:first-child { flex: 2; min-width: 0; }
.linked-row .form-select:nth-child(2) { flex: 1.5; min-width: 0; }
.lp-qty { width: 70px; flex-shrink: 0; text-align: center; }
</style>
