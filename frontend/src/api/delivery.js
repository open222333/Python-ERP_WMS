import client from './client'

export const deliveryApi = {
  // 外送訂單
  getOrders:        (params) => client.get('/delivery/orders', { params }),
  getOrder:         (id)     => client.get(`/delivery/orders/${id}`),
  updateOrderStatus:(id, s)  => client.put(`/delivery/orders/${id}/status`, { status: s }),  // PUT，非 PATCH

  // 主動拉取訂單
  syncOrders:       (platform) => client.post(`/delivery/sync/${platform}`),

  // 菜單同步
  syncMenu:         (platform) => client.post(`/delivery/menu/sync/${platform}`),

  // 平台設定
  getSettings:      (platform) => client.get(`/delivery/settings/${platform}`),
  saveSettings:     (platform, data) => client.put(`/delivery/settings/${platform}`, data),

  // 商品映射
  getMappings:      (params)   => client.get('/delivery/mappings', { params }),
  saveMapping:      (data)     => client.post('/delivery/mappings', data),
  deleteMapping:    (id)       => client.delete(`/delivery/mappings/${id}`),
}
