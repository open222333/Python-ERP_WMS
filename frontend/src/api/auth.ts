// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data } from './types'

export const authApi = {
  login:          (data: Data) => client.post('/auth/login', data),
  me:             ()           => client.get('/auth/me'),
  logout:         ()           => client.post('/auth/logout').catch(() => {}),
  changePassword: (data: Data) => client.post('/auth/change-password', data),
}
