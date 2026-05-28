import client from './client'

export const inboundApi = {
  getAll:      (params)        => client.get('/inbound/', { params }),
  getOne:      (id)            => client.get(`/inbound/${id}`),
  create:      (data)          => client.post('/inbound/', data),
  confirm:     (id)            => client.post(`/inbound/${id}/confirm`),
  complete:    (id)            => client.post(`/inbound/${id}/complete`),
  cancel:      (id)            => client.post(`/inbound/${id}/cancel`),
  addItem:     (id, data)      => client.post(`/inbound/${id}/item`, data),
  removeItem:  (id, itemId)    => client.delete(`/inbound/${id}/item/${itemId}`),
}
