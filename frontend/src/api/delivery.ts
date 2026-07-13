// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const deliveryApi = {
  // 外送訂單
  getOrders:        (params?: Params) => client.get('/delivery/orders', { params }),
  getOrder:         (id: Id)          => client.get(`/delivery/orders/${id}`),
  updateOrderStatus:(id: Id, s: string) => client.put(`/delivery/orders/${id}/status`, { status: s }),  // PUT，非 PATCH

  // 主動拉取訂單
  syncOrders:       (platform: string) => client.post(`/delivery/sync/${platform}`),

  // 菜單同步
  syncMenu:         (platform: string) => client.post(`/delivery/menu/sync/${platform}`),

  // 平台設定
  getSettings:      (platform: string)          => client.get(`/delivery/settings/${platform}`),
  saveSettings:     (platform: string, data: Data) => client.put(`/delivery/settings/${platform}`, data),

  // 商品映射
  getMappings:      (params?: Params) => client.get('/delivery/mappings', { params }),
  saveMapping:      (data: Data)      => client.post('/delivery/mappings', data),
  deleteMapping:    (id: Id)          => client.delete(`/delivery/mappings/${id}`),
}
