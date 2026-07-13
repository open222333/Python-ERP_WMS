<!-- [REFACTOR] 自 PosView.vue 拆出 -->
<template>
  <!-- Left: Items -->
  <div id="panel-products">
    <div id="product-toolbar">
      <div id="prod-search-wrap">
        <i class="bi bi-search"></i>
        <input v-model="prodSearch" type="text" id="prod-search" placeholder="搜尋名稱…" />
      </div>
    </div>

    <!-- Category tabs -->
    <div id="cat-tabs">
      <button v-for="tab in catTabs" :key="tab"
              class="cat-tab" :class="{ active: activeCat === tab }"
              @click="activeCat = tab">{{ tab }}</button>
    </div>

    <!-- Item grid -->
    <div id="product-grid">
      <div v-if="!selectedMenu" class="text-center text-muted py-4" style="grid-column:1/-1">
        <i class="bi bi-menu-button-wide fs-2"></i><p class="mt-2">請先從上方選擇菜單</p>
      </div>
      <div v-else-if="filteredItems.length === 0" class="text-center text-muted py-4" style="grid-column:1/-1">
        <i class="bi bi-inbox fs-2"></i><p class="mt-2">無符合品項</p>
      </div>
      <div v-for="item in filteredItems" :key="item._id"
           class="prod-card" @click="emit('item-click', item)">
        <div class="pc-name">{{ item.name }}</div>
        <div class="pc-sub">{{ item.category || '' }}</div>
        <div class="pc-price">NT$ {{ item.price }}</div>
        <div v-if="item.applied_groups?.length" class="pc-custom-badge">
          <i class="bi bi-sliders2"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  selectedMenu: string
  menus:        any[]
}>()

const emit = defineEmits<{
  (e: 'item-click', item: any): void
}>()

const prodSearch = ref('')
const activeCat  = ref('全部')

const activeMenuItems = computed(() => {
  if (!props.selectedMenu) return []
  const menu = props.menus.find((m: any) => m._id === props.selectedMenu)
  return ((menu?.items || []) as any[]).filter((i: any) => i.status === 1)
})

const catTabs = computed(() => {
  const cats = [...new Set(activeMenuItems.value.map((i: any) => (i.category || '其他') as string))]
  return ['全部', ...cats]
})

const filteredItems = computed(() => {
  let list = activeMenuItems.value
  if (activeCat.value && activeCat.value !== '全部') {
    list = list.filter((i: any) => (i.category || '其他') === activeCat.value)
  }
  if (prodSearch.value) {
    const q = prodSearch.value.toLowerCase()
    list = list.filter((i: any) => i.name.toLowerCase().includes(q))
  }
  return list
})

// 原 PosView onMenuChange()：切換菜單時重設分類與搜尋
watch(() => props.selectedMenu, () => {
  activeCat.value  = '全部'
  prodSearch.value = ''
})
</script>

<style scoped>
/* Product/Item panel */
#panel-products {
  display: grid; grid-template-rows: auto auto 1fr;
  flex: 1; min-height: 0; overflow: hidden; background: #f5f6fa;
}
#product-toolbar {
  padding: 10px 14px; background: #fff; border-bottom: 1px solid #e8eaf0;
  display: flex; gap: 8px; align-items: center;
}
#prod-search-wrap { position: relative; flex: 1; }
#prod-search-wrap i { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #9ca3af; pointer-events: none; }
#prod-search { width: 100%; border: 1px solid #e2e8f0; border-radius: 8px;
               padding: 7px 10px 7px 30px; font-size: .85rem; background: #f8f9fb; }
#prod-search:focus { outline: none; border-color: var(--accent); }
#prod-cat { border: 1px solid #e2e8f0; border-radius: 8px; padding: 7px 10px; font-size: .85rem; background: #f8f9fb; }
#cat-tabs { display: flex; gap: 6px; padding: 8px 14px; overflow-x: auto; background: #fff; border-bottom: 1px solid #e8eaf0; }
.cat-tab { padding: 4px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600;
           cursor: pointer; white-space: nowrap; border: 1.5px solid #e2e8f0;
           background: #f8f9fb; color: #6b7280; transition: .15s; }
.cat-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
#product-grid {
  flex: 1; min-height: 0; overflow-y: auto; padding: 14px;
  display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  grid-auto-rows: auto; gap: 10px; align-content: start;
  touch-action: pan-y;
}
.prod-card {
  background: #fff; border: 2px solid #edf0f7; border-radius: 12px;
  padding: 14px 10px 12px; text-align: center; cursor: pointer;
  transition: border-color .15s, transform .1s; user-select: none;
  position: relative;
}
.prod-card:hover  { border-color: var(--accent); }
.prod-card:active { transform: scale(.95); }
.pc-name  { font-size: 1rem; font-weight: 700; line-height: 1.35; color: #1e2235; }
.pc-sub   { font-size: .72rem; color: #9ca3af; margin-top: 4px; }
.pc-price { font-size: 1rem; font-weight: 800; color: var(--accent); margin-top: 6px; }
.pc-custom-badge {
  position: absolute; top: 6px; right: 8px;
  color: #6b7280; font-size: .72rem;
}
</style>
