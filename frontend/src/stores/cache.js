import { defineStore } from 'pinia'
import { ref } from 'vue'
import { warehouseApi } from '@/api/warehouse'
import { productApi }   from '@/api/product'

export const useCacheStore = defineStore('cache', () => {
  const warehouses  = ref([])
  const products    = ref([])
  const categories  = ref([])   // product categories

  async function loadWarehouses() {
    const { data } = await warehouseApi.getAll()
    warehouses.value = data.data || data || []
  }

  async function loadProducts() {
    const { data } = await productApi.getProducts()
    products.value = data.data || data || []
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
