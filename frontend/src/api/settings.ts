// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data } from './types'

export const settingsApi = {
  get:    ()           => client.get('/settings/'),
  update: (data: Data) => client.put('/settings/', data),
}
