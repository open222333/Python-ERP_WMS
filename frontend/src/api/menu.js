import client from './client'

export const menuApi = {
  getMenus:       ()      => client.get('/menu/'),
  createMenu:     (data)  => client.post('/menu/', data),
  updateMenu:     (id, d) => client.put(`/menu/${id}`, d),
  deleteMenu:     (id)    => client.delete(`/menu/${id}`),

  getItems:       (params)=> client.get('/menu/items', { params }),
  getItem:        (id)    => client.get(`/menu/items/${id}`),
  createItem:     (data)  => client.post('/menu/items', data),
  updateItem:     (id, d) => client.put(`/menu/items/${id}`, d),
  deleteItem:     (id)    => client.delete(`/menu/items/${id}`),
  toggleItem:     (id, v) => client.patch(`/menu/items/${id}/toggle`, { is_available: v }),

  getCategories:  ()      => client.get('/menu/categories'),
  createCategory: (data)  => client.post('/menu/categories', data),
  updateCategory: (id, d) => client.put(`/menu/categories/${id}`, d),
  deleteCategory: (id)    => client.delete(`/menu/categories/${id}`),

  getOptions:     (id)    => client.get(`/menu/items/${id}/options`),
  createOption:   (id, d) => client.post(`/menu/items/${id}/options`, d),
  deleteOption:   (oid)   => client.delete(`/menu/options/${oid}`),
}
