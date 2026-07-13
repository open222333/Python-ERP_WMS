// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id } from './types'

export const storeApi = {
  getAll:     ()                => client.get('/store/'),
  getOne:     (id: Id)          => client.get(`/store/${id}`),
  create:     (data: Data)      => client.post('/store/', data),
  update:     (id: Id, d: Data) => client.put(`/store/${id}`, d),
  delete:     (id: Id)          => client.delete(`/store/${id}`),
  getUsers:   (id: Id)          => client.get(`/store/${id}/users`),
  createUser: (id: Id, d: Data) => client.post(`/store/${id}/users`, d),

  // 店家角色模板
  roleGetAll:  ()                => client.get('/store/role/'),
  roleCreate:  (data: Data)      => client.post('/store/role/', data),
  roleUpdate:  (id: Id, d: Data) => client.put(`/store/role/${id}`, d),
  roleDelete:  (id: Id)          => client.delete(`/store/role/${id}`),
}
