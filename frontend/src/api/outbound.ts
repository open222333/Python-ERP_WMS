// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const outboundApi = {
  getAll:      (params?: Params)     => client.get('/outbound/', { params }),
  getOne:      (id: Id)              => client.get(`/outbound/${id}`),
  create:      (data: Data)          => client.post('/outbound/', data),
  confirm:     (id: Id)              => client.post(`/outbound/${id}/confirm`),
  complete:    (id: Id)              => client.post(`/outbound/${id}/complete`),
  cancel:      (id: Id)              => client.post(`/outbound/${id}/cancel`),
  addItem:     (id: Id, data: Data)  => client.post(`/outbound/${id}/item`, data),
  removeItem:  (id: Id, itemId: Id)  => client.delete(`/outbound/${id}/item/${itemId}`),
}
