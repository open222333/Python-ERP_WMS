// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Params } from './types'

export const inventoryApi = {
  getAll:    (params?: Params) => client.get('/inventory/',          { params }),
  adjust:    (data: Data)      => client.post('/inventory/adjust',   data),
  movements: (params?: Params) => client.get('/inventory/movement/', { params }),
  batchIO:   (data: Data)      => client.post('/inventory/batch',    data),   // QuickIO
}
