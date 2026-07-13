// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Params } from './types'

export const logApi = {
  getAll: (params?: Params) => client.get('/log/', { params }),
}
