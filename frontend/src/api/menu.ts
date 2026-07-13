// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const menuApi = {
  getMenus:       ()                 => client.get('/menu/'),
  createMenu:     (data: Data)       => client.post('/menu/', data),
  updateMenu:     (id: Id, d: Data)  => client.put(`/menu/${id}`, d),
  deleteMenu:     (id: Id)           => client.delete(`/menu/${id}`),

  getItems:       (params?: Params)  => client.get('/menu/items', { params }),
  getItem:        (id: Id)           => client.get(`/menu/items/${id}`),
  createItem:     (data: Data)       => client.post('/menu/items', data),
  updateItem:     (id: Id, d: Data)  => client.put(`/menu/items/${id}`, d),
  deleteItem:     (id: Id)           => client.delete(`/menu/items/${id}`),
  toggleItem:     (id: Id, v: boolean) => client.patch(`/menu/items/${id}/toggle`, { is_available: v }),

  getCategories:  ()                 => client.get('/menu/categories'),
  createCategory: (data: Data)       => client.post('/menu/categories', data),
  updateCategory: (id: Id, d: Data)  => client.put(`/menu/categories/${id}`, d),
  deleteCategory: (id: Id)           => client.delete(`/menu/categories/${id}`),

  getOptions:     (id: Id)           => client.get(`/menu/items/${id}/options`),
  createOption:   (id: Id, d: Data)  => client.post(`/menu/items/${id}/options`, d),
  deleteOption:   (oid: Id)          => client.delete(`/menu/options/${oid}`),
}
