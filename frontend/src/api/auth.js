import client from './client'

export const authApi = {
  login:          (data) => client.post('/auth/login', data),
  me:             ()     => client.get('/auth/me'),
  logout:         ()     => client.post('/auth/logout').catch(() => {}),
  changePassword: (data) => client.post('/auth/change-password', data),
}
