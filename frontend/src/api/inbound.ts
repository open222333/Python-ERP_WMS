// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const inboundApi = {
  getAll:      (params?: Params)        => client.get('/inbound/', { params }),
  getOne:      (id: Id)                 => client.get(`/inbound/${id}`),
  create:      (data: Data)             => client.post('/inbound/', data),
  confirm:     (id: Id)                 => client.post(`/inbound/${id}/confirm`),
  complete:    (id: Id)                 => client.post(`/inbound/${id}/complete`),
  cancel:      (id: Id)                 => client.post(`/inbound/${id}/cancel`),
  addItem:     (id: Id, data: Data)     => client.post(`/inbound/${id}/item`, data),
  removeItem:  (id: Id, itemId: Id)     => client.delete(`/inbound/${id}/item/${itemId}`),
}
