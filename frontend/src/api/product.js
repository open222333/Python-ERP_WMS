import client from './client'

export const productApi = {
  // 分類
  getCategories:   ()       => client.get('/product/category/'),
  createCategory:  (data)   => client.post('/product/category/', data),
  updateCategory:  (id, d)  => client.put(`/product/category/${id}`, d),
  deleteCategory:  (id)     => client.delete(`/product/category/${id}`),

  // 產品
  getProducts:     (params) => client.get('/product/', { params }),
  getProduct:      (id)     => client.get(`/product/${id}`),
  getByBarcode:    (code)   => client.get(`/product/barcode/${code}`),
  createProduct:   (data)   => client.post('/product/', data),
  updateProduct:   (id, d)  => client.put(`/product/${id}`, d),
  deleteProduct:   (id)     => client.delete(`/product/${id}`),
  exportProducts:  ()       => client.get('/product/export', { responseType: 'blob' }),
  importProducts:  (form)   => client.post('/product/import', form),
}
