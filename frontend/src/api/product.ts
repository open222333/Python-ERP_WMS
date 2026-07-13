// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const productApi = {
  // 分類
  getCategories:   ()                => client.get('/product/category/'),
  createCategory:  (data: Data)      => client.post('/product/category/', data),
  updateCategory:  (id: Id, d: Data) => client.put(`/product/category/${id}`, d),
  deleteCategory:  (id: Id)          => client.delete(`/product/category/${id}`),

  // 產品
  getProducts:     (params?: Params) => client.get('/product/', { params }),
  getProduct:      (id: Id)          => client.get(`/product/${id}`),
  getByBarcode:    (code: string)    => client.get(`/product/barcode/${code}`),
  createProduct:   (data: Data)      => client.post('/product/', data),
  updateProduct:   (id: Id, d: Data) => client.put(`/product/${id}`, d),
  deleteProduct:   (id: Id)          => client.delete(`/product/${id}`),
  exportProducts:  ()                => client.get('/product/export', { responseType: 'blob' }),
  importProducts:  (form: FormData)  => client.post('/product/import', form),
}
