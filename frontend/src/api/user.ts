// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const userApi = {
  // 使用者
  getAll:          (params?: Params) => client.get('/user/', { params }),
  getOne:          (id: Id)          => client.get(`/user/${id}`),
  create:          (data: Data)      => client.post('/user/', data),
  update:          (id: Id, d: Data) => client.put(`/user/${id}`, d),
  delete:          (id: Id)          => client.delete(`/user/${id}`),
  // 使用者模板
  getTemplates:    ()                => client.get('/user/templates/'),
  createTemplate:  (data: Data)      => client.post('/user/templates/', data),
  updateTemplate:  (id: Id, d: Data) => client.put(`/user/templates/${id}`, d),
  deleteTemplate:  (id: Id)          => client.delete(`/user/templates/${id}`),
}
