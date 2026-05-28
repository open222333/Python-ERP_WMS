import client from './client'

export const userApi = {
  // 使用者
  getAll:          (params) => client.get('/user/', { params }),
  getOne:          (id)     => client.get(`/user/${id}`),
  create:          (data)   => client.post('/user/', data),
  update:          (id, d)  => client.put(`/user/${id}`, d),
  delete:          (id)     => client.delete(`/user/${id}`),
  // 使用者模板
  getTemplates:    ()        => client.get('/user/templates/'),
  createTemplate:  (data)    => client.post('/user/templates/', data),
  updateTemplate:  (id, d)   => client.put(`/user/templates/${id}`, d),
  deleteTemplate:  (id)      => client.delete(`/user/templates/${id}`),
}
