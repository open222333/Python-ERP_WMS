// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { warehouseApi } from '@/api/warehouse'
import { productApi }   from '@/api/product'
import { fetchAllPages } from '@/api/paging'

export const useCacheStore = defineStore('cache', () => {
  const warehouses  = ref<any[]>([])
  const products    = ref<any[]>([])
  const categories  = ref<any[]>([])   // product categories

  async function loadWarehouses() {
    const { data } = await warehouseApi.getAll()
    warehouses.value = data.data || data || []
  }

  async function loadProducts() {
    // [U3] 分批取完整產品清單（原本只拿到前 200 筆，選單會找不到後面的產品）
    products.value = await fetchAllPages('/product/')
  }

  async function loadCategories() {
    const { data } = await productApi.getCategories()
    categories.value = data.data || data || []
  }

  async function loadAll() {
    await Promise.all([loadWarehouses(), loadProducts(), loadCategories()])
  }

  return { warehouses, products, categories, loadWarehouses, loadProducts, loadCategories, loadAll }
})
