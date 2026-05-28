import client from './client'

export const outboundApi = {
  getAll:      (params)     => client.get('/outbound/', { params }),
  getOne:      (id)         => client.get(`/outbound/${id}`),
  create:      (data)       => client.post('/outbound/', data),
  confirm:     (id)         => client.post(`/outbound/${id}/confirm`),
  complete:    (id)         => client.post(`/outbound/${id}/complete`),
  cancel:      (id)         => client.post(`/outbound/${id}/cancel`),
  addItem:     (id, data)   => client.post(`/outbound/${id}/item`, data),
  removeItem:  (id, itemId) => client.delete(`/outbound/${id}/item/${itemId}`),
}
