import client from './client'

export const storeApi = {
  getAll:     ()        => client.get('/store/'),
  getOne:     (id)      => client.get(`/store/${id}`),
  create:     (data)    => client.post('/store/', data),
  update:     (id, d)   => client.put(`/store/${id}`, d),
  delete:     (id)      => client.delete(`/store/${id}`),
  getUsers:   (id)      => client.get(`/store/${id}/users`),
  createUser: (id, d)   => client.post(`/store/${id}/users`, d),

  // 店家角色模板
  roleGetAll:  ()        => client.get('/store/role/'),
  roleCreate:  (data)    => client.post('/store/role/', data),
  roleUpdate:  (id, d)   => client.put(`/store/role/${id}`, d),
  roleDelete:  (id)      => client.delete(`/store/role/${id}`),
}
